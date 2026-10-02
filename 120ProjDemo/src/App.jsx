import './App.css'
import { useState } from "react";
import { NavBar } from "@/components/dashboard/NavBar";
import { ThemeProvider } from "@/components/theme-provider";
import { MainGraphView } from "@/components/dashboard/views/MainGraphView";

export default function App() {
  const [activeTab, setActiveTab] = useState("Main View");

  return (
    <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme">
      <div className="flex flex-col relative min-h-screen bg-background text-foreground p-6">
        
        <NavBar activeTab={activeTab} onTabChange={setActiveTab} />

        <main className="flex-1 flex flex-col p-6">
          {activeTab === "Main View" && <MainGraphView />}
        </main>

      </div>
    </ThemeProvider>
  )
}
