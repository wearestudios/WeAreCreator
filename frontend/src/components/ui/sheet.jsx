import * as React from "react"
import * as SheetPrimitive from "@radix-ui/react-dialog"
import { cva } from "class-variance-authority";
import { X } from "lucide-react"

import { cn } from "@/lib/utils"

const Sheet = SheetPrimitive.Root

const SheetTrigger = SheetPrimitive.Trigger

const SheetClose = SheetPrimitive.Close

const SheetPortal = SheetPrimitive.Portal

const SheetOverlay = React.forwardRef(({ className, ...props }, ref) => (
  <SheetPrimitive.Overlay
    className={cn(
      "fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className
    )}
    {...props}
    ref={ref} />
))
SheetOverlay.displayName = SheetPrimitive.Overlay.displayName

const sheetVariants = cva(
  "fixed z-50 flex flex-col gap-4 overflow-y-auto overscroll-contain border-white/10 bg-background/95 p-5 shadow-2xl shadow-black/60 backdrop-blur-xl grain-surface transition ease-in-out data-[state=closed]:duration-300 data-[state=open]:duration-500 data-[state=open]:animate-in data-[state=closed]:animate-out sm:p-6",
  {
    variants: {
      side: {
        top: "inset-x-0 top-0 max-h-[90dvh] border-b data-[state=closed]:slide-out-to-top data-[state=open]:slide-in-from-top",
        bottom:
          "inset-x-0 bottom-0 max-h-[90dvh] rounded-t-2xl border-t pb-[max(1.25rem,env(safe-area-inset-bottom))] data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom",
        left: "inset-y-0 left-0 h-full w-full border-r data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left sm:w-3/4 sm:max-w-sm",
        right:
          "inset-y-0 right-0 h-full w-full border-l data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right sm:w-3/4 sm:max-w-sm",
      },
    },
    defaultVariants: {
      side: "right",
    },
  }
)

/**
 * Put focus back where it came from.
 *
 * Radix restores focus to its own trigger, but most dialogs here are driven by
 * state (`open={dialog.kind === "accept"}`) with an ordinary button setting it,
 * so there is no trigger for Radix to return to and closing left focus on
 * <body>. For somebody on a keyboard that means the next Tab starts at the top
 * of the page rather than at the row they were working on.
 *
 * Capturing the active element as the content mounts covers both shapes: with
 * a real trigger this *is* that trigger, and without one it is whatever the
 * user actually pressed.
 */
function useReturnFocus() {
  // Captured during render, not in an effect: by the time effects run Radix
  // has already moved focus into the dialog, so an effect would record the
  // dialog itself and "returning" would be a no-op. This was the bug.
  const previous = React.useRef(undefined);
  if (previous.current === undefined && typeof document !== "undefined") {
    previous.current = document.activeElement;
  }
  React.useEffect(() => {
    return () => {
      const el = previous.current;
      // A trigger can unmount while the dialog is open — focusing a detached
      // node drops focus to <body>, which is the bug this exists to fix.
      if (el && typeof el.focus === "function" && document.contains(el)) {
        setTimeout(() => el.focus({ preventScroll: true }), 0);
      }
    };
  }, []);
}

const SheetContent = React.forwardRef(({ side = "right", className, children, ...props }, ref) => {
  useReturnFocus();
  return (
  <SheetPortal>
    <SheetOverlay />
    <SheetPrimitive.Content ref={ref} className={cn(sheetVariants({ side }), className)} {...props}>
      <SheetPrimitive.Close
        className="absolute right-3 top-3 z-10 grid h-11 w-11 place-items-center rounded-md opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember-500 focus-visible:ring-offset-2 disabled:pointer-events-none md:right-4 md:top-4 md:h-9 md:w-9">
        <X className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </SheetPrimitive.Close>
      {children}
    </SheetPrimitive.Content>
  </SheetPortal>
  );
})
SheetContent.displayName = SheetPrimitive.Content.displayName

const SheetHeader = ({
  className,
  ...props
}) => (
  <div
    className={cn("flex flex-col space-y-2 text-center sm:text-left", className)}
    {...props} />
)
SheetHeader.displayName = "SheetHeader"

const SheetFooter = ({
  className,
  ...props
}) => (
  <div
    className={cn("mt-auto flex flex-col-reverse gap-2 pt-2 sm:mt-0 sm:flex-row sm:justify-end sm:gap-0 sm:space-x-2 [&>*]:w-full sm:[&>*]:w-auto", className)}
    {...props} />
)
SheetFooter.displayName = "SheetFooter"

const SheetTitle = React.forwardRef(({ className, ...props }, ref) => (
  <SheetPrimitive.Title
    ref={ref}
    className={cn("text-lg font-semibold text-foreground", className)}
    {...props} />
))
SheetTitle.displayName = SheetPrimitive.Title.displayName

const SheetDescription = React.forwardRef(({ className, ...props }, ref) => (
  <SheetPrimitive.Description
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props} />
))
SheetDescription.displayName = SheetPrimitive.Description.displayName

export {
  Sheet,
  SheetPortal,
  SheetOverlay,
  SheetTrigger,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetFooter,
  SheetTitle,
  SheetDescription,
}
