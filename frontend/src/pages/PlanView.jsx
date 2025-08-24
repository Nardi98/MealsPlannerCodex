import React, { useContext, useEffect, useState } from 'react'
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

  const days = Object.keys(plan)
  if (days.length === 0) {
    return (
      <div>
        <h1>Plan View</h1>
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
    try {
      const resp = await request('/feedback/reject', {
        method: 'POST',
        body: JSON.stringify({ title: base }),
      })
      const replacement = resp.replacement || resp.title || null
      if (replacement) {
        const updated = {
          ...plan,
          [day]: plan[day].map((m, i) => (i === idx ? replacement : m)),
        }
        setPlan(updated)
        await persistPlan(updated)
      }
    } catch {
      // ignore
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
        <div className="swap-dialog" style={{ border: '1px solid #ccc', padding: '1rem', marginTop: '1rem' }}>
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
