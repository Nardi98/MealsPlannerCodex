import React, { useContext } from 'react'
import { AppContext } from '../App'

export default function PlanView() {
  const { plan } = useContext(AppContext)
  const days = Object.keys(plan)

  if (days.length === 0) {
    return (
      <div>
        <h1>Plan View</h1>
        <p>No plan available.</p>
      </div>
    )
  }

  return (
    <div>
      <h1>Plan View</h1>
      {days.map((day) => (
        <div key={day} style={{ marginBottom: '1rem' }}>
          <h3>{day}</h3>
          <ul>
            {plan[day].map((meal, idx) => (
              <li key={idx}>{meal}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}
