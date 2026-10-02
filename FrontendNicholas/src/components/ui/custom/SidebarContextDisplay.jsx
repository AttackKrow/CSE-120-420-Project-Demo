export function SidebarContextDisplay({selectedItem}) {
  return (
    <aside className="overflow-y-auto ">
      {selectedItem ? (
        <div>
          <div>{selectedItem.name}</div>
          <div>{selectedItem.id}</div>
        </div>
      ) : (
        <p>No item selected on left</p>
      )}
    </aside>
  )
} 