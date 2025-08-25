import React, { useContext, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { AppContext } from '../App'
import { mealPlansApi, recipesApi } from '../api'
import { request } from '../api/client'

export default function PlanView() {
  const { plan, setPlan, recipes, setRecipes } = useContext(AppContext)
  const [accepted, setAccepted] = useState({})
  const [swapSlot, setSwapSlot] = useState(null)
  const [keepDays, setKeepDays] = useState(1)
  const [allTitles, setAllTitles] = useState([])
  const [query, setQuery] = useState('')
  const toDateValue = (d) => d.toISOString().slice(0, 10)
  const today = new Date()
  const day = today.getDay()
  const diff = day === 0 ? -6 : 1 - day
  const defaultStart = new Date(today)
  defaultStart.setDate(today.getDate() + diff)
  const defaultEnd = new Date(defaultStart)
  defaultEnd.setDate(defaultStart.getDate() + 6)
  const [startDate, setStartDate] = useState(toDateValue(defaultStart))
  const [endDate, setEndDate] = useState(toDateValue(defaultEnd))
  const [loadMessage, setLoadMessage] = useState('')

  useEffect(() => {
    async function init() {
      if (Object.keys(plan).length === 0) {
        try {
          const fetched = await request('/plan')
          if (fetched && typeof fetched === 'object') {
            if (fetched.plan) {
              setPlan(fetched.plan)
              if (fetched.keep_days !== undefined) setKeepDays(fetched.keep_days)
            } else {
              setPlan(fetched)
            }
          }
        } catch {
          // ignore errors
        }
      }
      try {
        const settings = await request('/plan/settings')
        if (settings && settings.keep_days !== undefined) {
          setKeepDays(settings.keep_days)
        }
      } catch {
        // ignore errors
      }
      if (recipes.length === 0) {
        try {
          const data = await recipesApi.fetchAll()
          setRecipes(data)
          setAllTitles(data.map((r) => r.title))
        } catch {
          setRecipes([])
          setAllTitles([])
        }
      } else {
        setAllTitles(recipes.map((r) => r.title))
      }
    }
    init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  let successMessage
  try {
    const location = useLocation()
    successMessage = location.state?.message
  } catch {
    successMessage = undefined
  }
  const days = Object.keys(plan)

  const handleLoad = async (e) => {
    e.preventDefault()
    try {
      const fetched = await request(`/plan?start=${startDate}&end=${endDate}`)
      let newPlan
      if (fetched && typeof fetched === 'object') {
        newPlan = fetched.plan || fetched
      }
      if (newPlan && Object.keys(newPlan).length > 0) {
        setPlan(newPlan)
        setLoadMessage('')
      } else {
        setPlan({})
        setLoadMessage('No plan found for selected dates.')
      }
    } catch {
      setPlan({})
      setLoadMessage('No plan found for selected dates.')
    }
  }

  const persistPlan = async (titlePlan) => {
    try {
      let list = recipes
      if (list.length === 0) {
        list = await recipesApi.fetchAll()
        setRecipes(list)
      }
      const map = {}
      list.forEach((r) => {
        map[r.title] = r.id
      })
      const idPlan = {}
      Object.entries(titlePlan).forEach(([day, meals]) => {
        idPlan[day] = meals
          .map((t) => map[t.endsWith(' (leftover)') ? t.slice(0, -11) : t])
          .filter(Boolean)
      })
      const planDate = Object.keys(titlePlan)[0]
      await mealPlansApi.create({ plan_date: planDate, plan: idPlan })
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error(err)
    }
  }

  let maxMeals = 0
  let planEntries = []
  if (days.length > 0) {
    maxMeals = days.reduce((max, d) => Math.max(max, plan[d].length), 0)
    planEntries = days.map((d) => [d, plan[d]])
  }

  const getAge = (dayIdx, meal) => {
    if (!meal.endsWith(' (leftover)')) return null
    const base = meal.slice(0, -11)
    const dayDate = new Date(planEntries[dayIdx][0])
    for (let i = dayIdx - 1; i >= 0; i -= 1) {
      const [prevDay, prevMeals] = planEntries[i]
      if (prevMeals.includes(base)) {
        const prevDate = new Date(prevDay)
        return Math.round((dayDate.getTime() - prevDate.getTime()) / 86400000)
      }
    }
    return null
  }

  const handleAccept = async (day, idx) => {
    const meal = plan[day][idx]
    const base = meal.endsWith(' (leftover)') ? meal.slice(0, -11) : meal
    try {
      await request('/feedback/accept', {
        method: 'POST',
        body: JSON.stringify({ title: base }),
      })
    } catch {
      // ignore
    }
    setAccepted({ ...accepted, [`${day}-${idx}`]: true })
  }

  const handleReject = async (day, idx) => {
    const meal = plan[day][idx]
    const base = meal.endsWith(' (leftover)') ? meal.slice(0, -11) : meal
    const existing = new Set()
    Object.values(plan).forEach((meals) => {
      meals.forEach((m) => {
        const t = m.endsWith(' (leftover)') ? m.slice(0, -11) : m
        existing.add(t)
      })
    })
    let replacement = null
    for (let attempt = 0; attempt < 5; attempt += 1) {
      try {
        const resp = await request('/feedback/reject', {
          method: 'POST',
          body: JSON.stringify({ title: base }),
        })
        const candidate = resp.replacement || resp.title || null
        if (candidate && !existing.has(candidate)) {
          replacement = candidate
          break
        }
      } catch {
        break
      }
    }
    if (replacement) {
      const updated = {
        ...plan,
        [day]: plan[day].map((m, i) => (i === idx ? replacement : m)),
      }
      setPlan(updated)
      await persistPlan(updated)
    }
  }

  const handleSwap = (day, idx) => {
    setSwapSlot({ day, idx })
    setQuery('')
  }

  const confirmSwap = async (title) => {
    if (!swapSlot) return
    const { day, idx } = swapSlot
    const updated = {
      ...plan,
      [day]: plan[day].map((m, i) => (i === idx ? title : m)),
    }
    setPlan(updated)
    await persistPlan(updated)
    try {
      await request('/feedback/accept', {
        method: 'POST',
        body: JSON.stringify({ title }),
      })
    } catch {
      // ignore
    }
    setAccepted({ ...accepted, [`${day}-${idx}`]: true })
    setSwapSlot(null)
  }

  const isAccepted = (day, idx) => accepted[`${day}-${idx}`]
  const visibleTitles = allTitles.filter((t) =>
    t.toLowerCase().includes(query.toLowerCase())
  )

  return (
    <div>
      <h1>Plan View</h1>
      {successMessage && <p style={{ color: 'green' }}>{successMessage}</p>}
      <form onSubmit={handleLoad} style={{ marginBottom: '1rem' }}>
        <input
          type="date"
          aria-label="start date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
        />
        <input
          type="date"
          aria-label="end date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
        />
        <button type="submit">Load</button>
      </form>
      {loadMessage && <p>{loadMessage}</p>}
      {days.length === 0 ? (
        <p>No plan available.</p>
      ) : (
        <>
          <table>
            <thead>
              <tr>
                <th>Day</th>
                    {Array.from({ length: maxMeals }).map((_, i) => (
                      <th key={i}>Meal {i + 1}</th>
                    ))}
              </tr>
            </thead>
            <tbody>
              {planEntries.map(([day, meals], dayIdx) => {
                const dateObj = new Date(day)
                const weekday = dateObj.toLocaleDateString(undefined, { weekday: 'long' })
                const formatted = dateObj.toLocaleDateString()
                return (
                  <tr key={day}>
                    <td>
                      {weekday}
                      <div style={{ fontSize: '0.8em' }}>{formatted}</div>
                    </td>
                    {Array.from({ length: maxMeals }).map((_, idx) => {
                      if (idx >= meals.length) return <td key={idx} />
                      const meal = meals[idx]
                      const age = getAge(dayIdx, meal)
                      return (
                        <td key={idx}>
                          <div>{meal}</div>
                          {age !== null && age >= keepDays && (
                            <div style={{ color: 'red' }}>
                              {`${meal} is ${age} days old (max ${keepDays})`}
                            </div>
                          )}
                          {isAccepted(day, idx) ? (
                            <button
                              type="button"
                              disabled
                              style={{ backgroundColor: 'green', color: 'white' }}
                            >
                              Accepted
                            </button>
                          ) : (
                            <div>
                              <button type="button" onClick={() => handleAccept(day, idx)}>
                                Accept
                              </button>
                              <button type="button" onClick={() => handleReject(day, idx)}>
                                Reject
                              </button>
                              <button type="button" onClick={() => handleSwap(day, idx)}>
                                Swap
                              </button>
                              </div>
                            )}
                          </td>
                        )
                    })}
                  </tr>
                )
              })}
            </tbody>
          </table>
          {swapSlot && (
            <div
              className="swap-dialog"
              style={{ border: '1px solid #ccc', padding: '1rem', marginTop: '1rem' }}
            >
              <h3>Swap Recipe</h3>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search Recipe"
              />
                <ul>
                  {visibleTitles.map((t) => (
                    <li key={t}>
                      <button type="button" onClick={() => confirmSwap(t)}>
                        {t}
                      </button>
                    </li>
                  ))}
                </ul>
              <button type="button" onClick={() => setSwapSlot(null)}>
                Cancel
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

