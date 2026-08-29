import React from 'react'
import {
  MealActionModal,
  OverwriteConfirmModal,
  MealPlanCalendar,
  GenerationForm,
} from '../components'
import MobileCollapse from '../components/MobileCollapse'
import { tagsApi } from '../api/tagsApi'
import { ingredientsApi } from '../api/ingredientsApi'
import { useMealPlan } from '../hooks/useMealPlan'
import { useGeneration } from '../hooks/useGeneration'
import { useSideDishes } from '../hooks/useSideDishes'
import { PageTour } from '../tutorial/PageTour'

export default function MealPlanPage() {
  const [tags, setTags] = React.useState([])
  const [ingredients, setIngredients] = React.useState([])
  const [activeCell, setActiveCell] = React.useState(null)

  const {
    weekDays,
    isToday,
    fmt,
    plan,
    setPlan,
    changeWeek,
    goToToday,
    cancelSwap,
    handleAccept,
    handleReject,
    handleSwap,
    armedCell,
    armSwap,
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

  React.useEffect(() => {
    async function loadIngredients() {
      try {
        const data = await ingredientsApi.fetchAll()
        setIngredients(data)
      } catch (err) {
        console.error('Failed to load ingredients', err)
      }
    }
    loadIngredients()
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
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-medium" style={{ color: 'var(--text-strong)' }}>
        Meal Plan
      </h1>
      <PageTour id="meal-plan" />
      {/* Calendar first at every width: it is what the page is about, and on a
          phone the settings sat between the heading and the plan you came to
          look at. Visual order now matches the DOM, so the tab order agrees. */}
      <div data-plan-section>
      <MealPlanCalendar
        weekDays={weekDays}
        plan={plan}
        fmt={fmt}
        isToday={isToday}
        onSelectCell={setActiveCell}
        onAccept={acceptCell}
        onReject={rejectCell}
        onChangeWeek={changeWeek}
        onArmSwap={armSwap}
        onCancelSwap={cancelSwap}
        onToday={goToToday}
        armedCell={armedCell}
      />
      </div>
      <div data-plan-section>
      <MobileCollapse title="Plan settings" tourId="mealplan-settings-toggle" defaultOpen>
      <GenerationForm
        form={generation.form}
        tags={tags}
        ingredients={ingredients}
        message={generation.message}
        error={generation.error}
        onChange={generation.handleChange}
        onRangeChange={generation.handleRangeChange}
        onPresetChange={generation.handlePresetChange}
        onAvoidChange={generation.handleAvoidChange}
        onReduceChange={generation.handleReduceChange}
        onFridgeChange={generation.handleFridgeChange}
        onSubmit={generation.handleGenerate}
      />
      </MobileCollapse>
      </div>
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
