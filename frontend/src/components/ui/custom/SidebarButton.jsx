import { XIcon,PencilIcon } from "lucide-react"
import { Button } from "@/components/ui/button"

export function SidebarButton({buttonName, onClick}) {
  return (
    <div className={'flex w-full items-center overflow-hidden border border-input bg-background shadow-sm'}>
      <Button variant="ghost" 
        className="flex-1 justify-start rounded-none"
        onClick={onClick}
      >
        {buttonName}
      </Button>
      <Button variant="ghost" size="icon" aria-label="Rename">
        <PencilIcon/>
      </Button>
      <Button variant="ghost" size="icon" aria-label="Delete">
        <XIcon/>
      </Button>
    </div>
  )
}
