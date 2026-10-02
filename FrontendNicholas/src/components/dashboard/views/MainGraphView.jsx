import BasicPlot from "@/components/graphing/BasicPlot";
import { useState } from "react";
import { SidebarViewSelector } from "@/components/ui/custom/SidebarViewSelector";
import { SidebarContextDisplay } from "@/components/ui/custom/SidebarContextDisplay";


export function MainGraphView({backendData, isLoading}) {

  const [selectedItem, setSelectedItem] = useState(null);

  const listItems = [{id: 1, name: "View 1"}, {id: 2, name: "View 2"}, {id: 3, name: "View 3"}];

  return (
    <div className="flex-1 w-full flex flex-col overflow-hidden">
      <div className="flex-1 grid grid-cols-[250px_1fr_150px] min-h-0">


        {/* Left sidebar for item selection */}
        <SidebarViewSelector listItems={listItems} setSelectedItem={setSelectedItem} />

        {/* Center Graph */}
        <main className="relative overflow-hidden p-4 h-full w-full">
          <BasicPlot data={selectedItem ? [selectedItem] : []} />
        </main>

        {/* Right sidebar for context display */}
        <SidebarContextDisplay selectedItem={selectedItem} />

      </div>

      {/* Bottom reserved space */}
      <div className="h=64 p-4 flex items-center justify-center">
        <div className="text-sm font-medium">
          {isLoading ? (
            <span className="animate-pulse text-yellow-500">Loading data...</span>
          ) : backendData ?(
            <span className="text-green-500">Data received</span>
          ) : (
            <span className="text-red-500">No data available</span>
          )}
        </div>
      </div>

    </div>
  )
}
