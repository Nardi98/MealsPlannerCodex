import React, { useContext, useState } from 'react'
import { AppContext } from '../App'
import { mealPlansApi } from '../api'

export default function NewPlan() {
  const { recipes, setPlan } = useContext(AppContext)
  const [startDate, setStartDate] = useState('')
  const [days, setDays] = useState(7)
  const [mealsPerDay, setMealsPerDay] = useState(1)
  const [epsilon, setEpsilon] = useState(0)
  const [seasonalityWeight, setSeasonalityWeight] = useState(1)
  const [recencyWeight, setRecencyWeight] = useState(1)
  const [tagPenaltyWeight, setTagPenaltyWeight] = useState(1)
  const [bulkBonusWeight, setBulkBonusWeight] = useState(1)
  const [bulkLeftovers, setBulkLeftovers] = useState(true)
  const [keepDays, setKeepDays] = useState(7)
  const [avoidTags, setAvoidTags] = useState('')
  const [reduceTags, setReduceTags] = useState('')
  const [error, setError] = useState(null)

  const generate = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      const params = {
        start: startDate,
        days: Number(days),
        meals_per_day: Number(mealsPerDay),
        epsilon: Number(epsilon),
        seasonality_weight: Number(seasonalityWeight),
        recency_weight: Number(recencyWeight),
        tag_penalty_weight: Number(tagPenaltyWeight),
        bulk_bonus_weight: Number(bulkBonusWeight),
        bulk_leftovers: Boolean(bulkLeftovers),
        keep_days: Number(keepDays),
        avoid_tags: avoidTags.split(',').map((t) => t.trim()).filter(Boolean),
        reduce_tags: reduceTags.split(',').map((t) => t.trim()).filter(Boolean),
      }
      const plan = await mealPlansApi.generate(params)
      setPlan(plan)

      const idPlan = {}
      Object.entries(plan).forEach(([day, meals]) => {
        idPlan[day] = meals
          .map((meal) => {
            const base = meal.endsWith(' (leftover)') ? meal.slice(0, -11) : meal
            const match = recipes.find((r) => r.title === base)
            return match && match.id
          })
          .filter(Boolean)
      })

      const { start: _start, ...settings } = params
      await mealPlansApi.create({
        plan_date: startDate,
        plan: idPlan,
        ...settings,
      })
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <h1>New Plan</h1>
      <form onSubmit={generate}>
        {error && <p style={{ color: 'red' }}>{error}</p>}
        <div>
          <label>Start Date </label>
          <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </div>
        <div>
          <label>Days </label>
          <input type="number" min="1" value={days} onChange={(e) => setDays(Number(e.target.value))} />
        </div>
        <div>
          <label>Meals per Day </label>
          <input type="number" min="1" value={mealsPerDay} onChange={(e) => setMealsPerDay(Number(e.target.value))} />
        </div>
        <details>
          <summary>Advanced Options</summary>
          <div>
            <label>ε </label>
            <input type="number" step="0.1" value={epsilon} onChange={(e) => setEpsilon(e.target.value)} />
          </div>
          <div>
            <label>Seasonality Weight </label>
            <input type="number" step="0.1" value={seasonalityWeight} onChange={(e) => setSeasonalityWeight(e.target.value)} />
          </div>
          <div>
            <label>Recency Weight </label>
            <input type="number" step="0.1" value={recencyWeight} onChange={(e) => setRecencyWeight(e.target.value)} />
          </div>
          <div>
            <label>Tag Penalty Weight </label>
            <input type="number" step="0.1" value={tagPenaltyWeight} onChange={(e) => setTagPenaltyWeight(e.target.value)} />
          </div>
          <div>
            <label>Bulk-Prep Bonus Weight </label>
            <input type="number" step="0.1" value={bulkBonusWeight} onChange={(e) => setBulkBonusWeight(e.target.value)} />
          </div>
          <div>
            <label>Bulk Leftovers </label>
            <input type="checkbox" checked={bulkLeftovers} onChange={(e) => setBulkLeftovers(e.target.checked)} />
          </div>
          <div>
            <label>Keep Days </label>
            <input type="number" min="1" value={keepDays} onChange={(e) => setKeepDays(e.target.value)} />
          </div>
          <div>
            <label>Avoid Tags </label>
            <input value={avoidTags} onChange={(e) => setAvoidTags(e.target.value)} placeholder="comma separated" />
          </div>
          <div>
            <label>Reduce Tags </label>
            <input value={reduceTags} onChange={(e) => setReduceTags(e.target.value)} placeholder="comma separated" />
          </div>
        </details>
        <button type="submit">Generate Plan</button>
      </form>
    </div>
  )
}
