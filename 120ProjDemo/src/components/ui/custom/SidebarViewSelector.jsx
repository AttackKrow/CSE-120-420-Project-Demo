import { SidebarButton } from "@/components/ui/custom/SidebarButton";

export function SidebarViewSelector({listItems, setSelectedItem}) {
  return (
    <aside className="overflow-y-auto p-1 flex flex-col gap-1">
      {listItems.map((item) => (
        <SidebarButton 
        buttonName={item.name} 
        key={item.id} 
        onClick={() => setSelectedItem(item)} />
      ))}
    </aside>
  )
}