import './App.css'
import { useState, useEffect } from "react";
import { NavBar } from "@/components/dashboard/NavBar";
import { ThemeProvider } from "@/components/theme-provider";
import { MainGraphView } from "@/components/dashboard/views/MainGraphView";

export default function App() {
  const [activeTab, setActiveTab] = useState("Main View");

  /* FastAPI integration boilerplate */

  const[backendData, setBackendData] = useState(null);
  const[isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchBackendData = async () => {
      try {
        const response = await fetch('/api/data');
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const result = await response.json();
        setBackendData(result.data);
      } catch (error) {
        console.error("Failed to fetch data:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchBackendData();
  }, []); 
  
  

  return (
    <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme">
      <div className="flex flex-col relative min-h-screen bg-background text-foreground p-6">
        
        <NavBar activeTab={activeTab} onTabChange={setActiveTab} />

        <main className="flex-1 flex flex-col p-6">
          {activeTab === "Main View" && (
            <MainGraphView data={backendData} isLoading={isLoading} />
            )}
        </main>

      </div>
    </ThemeProvider>
  )
}
