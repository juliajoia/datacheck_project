import * as DropdownPrimitive from "@radix-ui/react-dropdown-menu";
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";
import { cn } from "@/lib/utils";

export const DropdownMenu = DropdownPrimitive.Root;
export const DropdownMenuTrigger = DropdownPrimitive.Trigger;
export const DropdownMenuLabel = ({ className, ...p }: ComponentPropsWithoutRef<typeof DropdownPrimitive.Label>) => (
  <DropdownPrimitive.Label className={cn("px-2 py-1.5 text-sm font-semibold", className)} {...p} />
);
export const DropdownMenuSeparator = () => <DropdownPrimitive.Separator className="-mx-1 my-1 h-px bg-border" />;

export const DropdownMenuContent = forwardRef<ElementRef<typeof DropdownPrimitive.Content>, ComponentPropsWithoutRef<typeof DropdownPrimitive.Content>>(
  ({ className, sideOffset = 8, ...p }, ref) => (
    <DropdownPrimitive.Portal>
      <DropdownPrimitive.Content
        ref={ref}
        sideOffset={sideOffset}
        className={cn("z-50 min-w-[14rem] rounded-xl border bg-popover p-1.5 text-popover-foreground shadow-lg animate-in fade-in-0 zoom-in-95", className)}
        {...p}
      />
    </DropdownPrimitive.Portal>
  ),
);
DropdownMenuContent.displayName = "DropdownMenuContent";

export const DropdownMenuItem = forwardRef<ElementRef<typeof DropdownPrimitive.Item>, ComponentPropsWithoutRef<typeof DropdownPrimitive.Item>>(
  ({ className, ...p }, ref) => (
    <DropdownPrimitive.Item
      ref={ref}
      className={cn("flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-sm outline-none data-[highlighted]:bg-accent [&_svg]:size-4", className)}
      {...p}
    />
  ),
);
DropdownMenuItem.displayName = "DropdownMenuItem";
