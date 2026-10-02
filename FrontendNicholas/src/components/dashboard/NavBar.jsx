import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ModeToggle } from "@/components/dark-mode-toggle";

export function NavBar({ activeTab, onTabChange }) {
  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background/95 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <span className="font-bold text-lg">DBBench</span>
        <Tabs value={activeTab} onValueChange={onTabChange}>
          <TabsList variant="line">
            <TabsTrigger value="Main View">Main View</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
      <ModeToggle />
    </header>
  )
}
