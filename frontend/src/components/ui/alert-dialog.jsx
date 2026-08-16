import * as React from "react"
import * as AlertDialogPrimitive from "@radix-ui/react-alert-dialog"

import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"

const AlertDialog = AlertDialogPrimitive.Root

const AlertDialogTrigger = AlertDialogPrimitive.Trigger

const AlertDialogPortal = AlertDialogPrimitive.Portal

const AlertDialogOverlay = React.forwardRef(({ className, ...props }, ref) => (
  <AlertDialogPrimitive.Overlay
    className={cn(
      "fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className
    )}
    {...props}
    ref={ref} />
))
AlertDialogOverlay.displayName = AlertDialogPrimitive.Overlay.displayName

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
  // dialog itself and "returning" would be a no-op.
  const previous = React.useRef(undefined);
  if (previous.current === undefined && typeof document !== "undefined") {
    previous.current = document.activeElement;
  }
  // Belt and braces alongside the handler above. Radix's own FocusScope blurs
  // on unmount and lands last, so this runs two frames later — after React has
  // re-rendered the list the trigger lives in, which is what detaches the
  // original node — and re-finds the trigger by its testid.
  React.useEffect(
    () => () => {
      const el = previous.current;
      if (!el || typeof el.focus !== "function") return;
      const testid = el.dataset ? el.dataset.testid : null;
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          if (document.activeElement && document.activeElement !== document.body) return;
          const target = document.contains(el)
            ? el
            : testid
              ? document.querySelector(`[data-testid="${testid}"]`)
              : null;
          target?.focus({ preventScroll: true });
        }),
      );
    },
    [],
  );

  // Returned as an `onCloseAutoFocus` handler rather than done in a cleanup:
  // Radix's own FocusScope also restores focus on unmount and runs last, so an
  // unmount-time restore was silently overwritten with <body>. preventDefault
  // stops Radix doing its own thing on top of ours.
  //
  // The retry matters. Closing usually re-renders the list the trigger lives
  // in, and React can replace that button with a fresh node — focus lands on a
  // detached element and falls to <body>. So we focus now, then check again on
  // the next frame and re-find the trigger by its testid if the node it was
  // has gone.
  return React.useCallback((event) => {
    const el = previous.current;
    if (!el || typeof el.focus !== "function") return;
    event.preventDefault();
    const testid = el.dataset ? el.dataset.testid : null;
    const focus = (node) => node && node.focus({ preventScroll: true });
    if (document.contains(el)) focus(el);
    requestAnimationFrame(() => {
      if (document.activeElement && document.activeElement !== document.body) return;
      focus(
        document.contains(el)
          ? el
          : testid
            ? document.querySelector(`[data-testid="${testid}"]`)
            : null,
      );
    });
  }, []);
}

const AlertDialogContent = React.forwardRef(({ className, ...props }, ref) => {
  const onCloseAutoFocus = useReturnFocus();
  return (
  <AlertDialogPortal>
    <AlertDialogOverlay />
    <AlertDialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed inset-x-0 bottom-0 top-auto z-50 flex max-h-[90dvh] w-full translate-x-0 translate-y-0 flex-col gap-4 overflow-y-auto overscroll-contain rounded-t-2xl border border-white/10 bg-background/95 p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] shadow-2xl shadow-black/60 backdrop-blur-xl grain-surface duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom sm:inset-x-auto sm:bottom-auto sm:left-[50%] sm:top-[50%] sm:max-h-[85vh] sm:max-w-lg sm:translate-x-[-50%] sm:translate-y-[-50%] sm:rounded-lg sm:p-6 sm:pb-6 sm:data-[state=closed]:zoom-out-95 sm:data-[state=open]:zoom-in-95",
        className
      )}
      {...props}
      onCloseAutoFocus={props.onCloseAutoFocus || onCloseAutoFocus} />
  </AlertDialogPortal>
  );
})
AlertDialogContent.displayName = AlertDialogPrimitive.Content.displayName

const AlertDialogHeader = ({
  className,
  ...props
}) => (
  <div
    className={cn("flex flex-col space-y-2 text-center sm:text-left", className)}
    {...props} />
)
AlertDialogHeader.displayName = "AlertDialogHeader"

const AlertDialogFooter = ({
  className,
  ...props
}) => (
  <div
    className={cn("mt-auto flex flex-col-reverse gap-2 pt-2 sm:mt-0 sm:flex-row sm:justify-end sm:gap-0 sm:space-x-2 [&>*]:w-full sm:[&>*]:w-auto", className)}
    {...props} />
)
AlertDialogFooter.displayName = "AlertDialogFooter"

const AlertDialogTitle = React.forwardRef(({ className, ...props }, ref) => (
  <AlertDialogPrimitive.Title ref={ref} className={cn("text-lg font-semibold", className)} {...props} />
))
AlertDialogTitle.displayName = AlertDialogPrimitive.Title.displayName

const AlertDialogDescription = React.forwardRef(({ className, ...props }, ref) => (
  <AlertDialogPrimitive.Description
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props} />
))
AlertDialogDescription.displayName =
  AlertDialogPrimitive.Description.displayName

const AlertDialogAction = React.forwardRef(({ className, ...props }, ref) => (
  <AlertDialogPrimitive.Action ref={ref} className={cn(buttonVariants(), className)} {...props} />
))
AlertDialogAction.displayName = AlertDialogPrimitive.Action.displayName

const AlertDialogCancel = React.forwardRef(({ className, ...props }, ref) => (
  <AlertDialogPrimitive.Cancel
    ref={ref}
    className={cn(buttonVariants({ variant: "outline" }), "mt-2 sm:mt-0", className)}
    {...props} />
))
AlertDialogCancel.displayName = AlertDialogPrimitive.Cancel.displayName

export {
  AlertDialog,
  AlertDialogPortal,
  AlertDialogOverlay,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
}
