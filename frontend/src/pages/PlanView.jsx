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
  const getWeekRange = () => {
    const today = new Date()
    const day = today.getDay()
    const monday = new Date(today)
    monday.setDate(today.getDate() - ((day + 6) % 7))
    const sunday = new Date(monday)
    sunday.setDate(monday.getDate() + 6)
    const format = (d) => d.toISOString().split('T')[0]
    return { start: format(monday), end: format(sunday) }
  }
  const { start: defaultStart, end: defaultEnd } = getWeekRange()
  const [startDate, setStartDate] = useState(defaultStart)
  const [endDate, setEndDate] = useState(defaultEnd)

  const loadPlanRange = async () => {
    if (!startDate || !endDate) return
    try {
      const fetched = await request(
        `/plan?start_date=${startDate}&end_date=${endDate}`
      )
      if (fetched && typeof fetched === 'object') {
        const p = fetched.plan || fetched
        const titlePlan = {}
        const acceptedInit = {}
        Object.entries(p).forEach(([day, meals]) => {
          titlePlan[day] = meals.map((m, idx) => {
            const title = m.recipe || m.title || m
            if (m.accepted) acceptedInit[`${day}-${idx}`] = true
            return title
          })
        })
        setPlan(titlePlan)
        setAccepted(acceptedInit)
        if (fetched.keep_days !== undefined) setKeepDays(fetched.keep_days)
      }
    } catch {
      // ignore errors
    }
  }

  useEffect(() => {
    async function init() {
      if (Object.keys(plan).length === 0) {
        await loadPlanRange()
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

  const persistPlan = async (titlePlan) => {
    let idPlan
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
      idPlan = {}
      Object.entries(titlePlan).forEach(([day, meals]) => {
        idPlan[day] = meals
          .map((t) => map[t.endsWith(' (leftover)') ? t.slice(0, -11) : t])
          .filter(Boolean)
      })
      const planDate = Object.keys(titlePlan)[0]
      await mealPlansApi.create({ plan_date: planDate, plan: idPlan })
    } catch (err) {
      if (err.conflicts) {
        const msg = `Overwrite existing plans on ${err.conflicts.join(', ')}?`
        if (window.confirm(msg)) {
          const planDate = Object.keys(titlePlan)[0]
          await mealPlansApi.create(
            { plan_date: planDate, plan: idPlan },
            { force: true }
          )
        }
      } else {
        // eslint-disable-next-line no-console
        console.error(err)
      }
    }
  }

  if (days.length === 0) {
    return (
      <div>
        <h1>Plan View</h1>
        {successMessage && <p style={{ color: 'green' }}>{successMessage}</p>}
        <div>
          <input
            type="date"
            aria-label="Start date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
          <input
            type="date"
            aria-label="End date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
          <button type="button" onClick={loadPlanRange}>
            Load Plan
          </button>
        </div>
        <p>No plan available.</p>
      </div>
    )
  }

  const maxMeals = days.reduce((max, d) => Math.max(max, plan[d].length), 0)
  const planEntries = days.map((d) => [d, plan[d]])

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
    try {
      await mealPlansApi.accept(day, idx + 1, true)
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
      const newAccepted = { ...accepted }
      delete newAccepted[`${day}-${idx}`]
      setAccepted(newAccepted)
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
      await mealPlansApi.accept(day, idx + 1, true)
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
      <div>
        <input
          type="date"
          aria-label="Start date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
        />
        <input
          type="date"
          aria-label="End date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
        />
        <button type="button" onClick={loadPlanRange}>
          Load Plan
        </button>
      </div>
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
          {planEntries.map(([day, meals], dayIdx) => (
            <tr key={day}>
              <td>{day}</td>
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
          ))}
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
    </div>
  )
}

