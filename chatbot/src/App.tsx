import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'
import { ChatApp } from './components'
import LangGraphChatApp from './components/LanggraphAchatApp'

function App() {
 
  return (
    <>
      <div className='flex-1 border'>
        <LangGraphChatApp/>
      </div>
       
    </>
  )
}

export default App
