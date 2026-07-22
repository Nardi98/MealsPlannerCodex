import React from 'react'
import {
  MealActionModal,
  OverwriteConfirmModal,
  MealPlanCalendar,
  GenerationForm,
} from '../components'
import { tagsApi } from '../api/tagsApi'
import { useMealPlan } from '../hooks/useMealPlan'
import { useGeneration } from '../hooks/useGeneration'
import { useSideDishes } from '../hooks/useSideDishes'

export default function MealPlanPage() {
  const [tags, setTags] = React.useState([])
  const [activeCell, setActiveCell] = React.useState(null)

  const {
    weekDays,
    isToday,
    fmt,
    plan,
    setPlan,
    changeWeek,
    handleAccept,
    handleReject,
    handleSwap,
  } = useMealPlan({ setError: (msg) => generation.setError(msg) })

  const generation = useGeneration({ setPlan })

  const sides = useSideDishes({
    plan,
    setPlan,
    setError: (msg) => generation.setError(msg),
  })

  React.useEffect(() => {
    async function loadTags() {
      try {
        const data = await tagsApi.fetchAll()
        setTags(data.map((t) => t.name))
      } catch (err) {
        console.error('Failed to load tags', err)
      }
    }
    loadTags()
  }, [])

  const closeCell = () => setActiveCell(null)

  const acceptCell = async (cell = activeCell) => {
    await handleAccept(cell)
    closeCell()
  }
  const rejectCell = (cell = activeCell) => handleReject(cell)

  const activeMeal = activeCell
    ? plan[activeCell.date]?.[activeCell.mealIndex]
    : null
  const activeMealType = activeCell?.mealIndex === 1 ? 'dinner' : 'lunch'

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-medium" style={{ color: 'var(--text-strong)' }}>
        Meal Plan
      </h1>
      <MealPlanCalendar
        weekDays={weekDays}
        plan={plan}
        fmt={fmt}
        isToday={isToday}
        onSelectCell={setActiveCell}
        onAccept={acceptCell}
        onReject={rejectCell}
        onChangeWeek={changeWeek}
      />
      <GenerationForm
        form={generation.form}
        tags={tags}
        message={generation.message}
        error={generation.error}
        onChange={generation.handleChange}
        onRangeChange={generation.handleRangeChange}
        onPresetChange={generation.handlePresetChange}
        onAvoidChange={generation.handleAvoidChange}
        onReduceChange={generation.handleReduceChange}
        onSubmit={generation.handleGenerate}
      />
      {generation.showOverwriteModal && (
        <OverwriteConfirmModal
          onCancel={generation.handleCancelOverwrite}
          onConfirm={generation.handleConfirmOverwrite}
          title="Overwrite Existing Plans"
          message="The following dates already have meal plans. Overwrite them?"
          items={generation.conflictDays}
        />
      )}
      {activeCell && (
        <MealActionModal
          date={activeCell.date}
          meal={activeMealType}
          recipe={activeMeal?.recipe}
          sides={activeMeal?.side_recipes || []}
          accepted={activeMeal?.accepted}
          onAccept={acceptCell}
          onReject={rejectCell}
          onSwap={(newTitle) => handleSwap(activeCell, newTitle)}
          onAddSide={() => sides.handleAddSide(activeCell)}
          onRejectSide={(sideIndex) => sides.handleRejectSide(activeCell, sideIndex)}
          onRemoveSide={(sideIndex) => sides.handleRemoveSide(activeCell, sideIndex)}
          onSwapSide={(sideIndex, newTitle) =>
            sides.handleSwapSide(activeCell, sideIndex, newTitle)
          }
          onClose={closeCell}
        />
      )}
    </div>
  )
}
