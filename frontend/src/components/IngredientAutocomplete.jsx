import React, { useEffect, useId, useState } from 'react'
import { ingredientsApi } from '../api'

export default function IngredientAutocomplete({ value, onChange, placeholder }) {
  const [suggestions, setSuggestions] = useState([])
  const [inputValue, setInputValue] = useState(value || '')
  const listId = useId()

  useEffect(() => {
    setInputValue(value || '')
  }, [value])

  useEffect(() => {
    let active = true
    async function load() {
      if (!inputValue) {
        setSuggestions([])
        return
      }
      try {
        const results = await ingredientsApi.search(inputValue)
        if (active) setSuggestions(results)
      } catch (e) {
        console.error('Failed to load ingredient suggestions', e)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [inputValue])

  return (
    <>
      <input
        list={listId}
        value={inputValue}
        placeholder={placeholder}
        onChange={(e) => {
          setInputValue(e.target.value)
          onChange(e.target.value)
        }}
      />
      <datalist id={listId}>
        {suggestions.map((name) => (
          <option key={name} value={name} />
        ))}
      </datalist>
    </>
  )
}
