import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-button text-meta font-[var(--btn-weight)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-60 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:
          "border border-input bg-tint/[0.02] hover:bg-muted hover:text-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-muted hover:text-foreground",
        link: "text-primary underline-offset-4 hover:underline",
        // The app's three. `urgent` is the single most pressing action on a
        // card and there is at most one: the red is `--urgent` (#C41E27) on
        // every surface rather than the brand #FF2731, because a white word
        // on the brand red is 3.76:1 and on #C41E27 it is 5.90:1. `solid` is navy, the
        // ordinary action; `quiet` is the warm-grey ghost.
        urgent: "bg-urgent text-brand-white hover:bg-urgent/90",
        solid: "bg-primary text-primary-foreground hover:bg-primary-hover",
        quiet: "bg-wash-warm text-heading hover:bg-muted",
      },
      size: {
        default: "min-h-[2.75rem] px-4 py-2 md:min-h-0 md:h-9",
        sm: "min-h-[2.75rem] px-3 text-meta md:min-h-0 md:h-8",
        lg: "min-h-[2.75rem] px-8 md:h-10",
        icon: "h-11 w-11 md:h-9 md:w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

const Button = React.forwardRef(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      {...props} />
  );
})
Button.displayName = "Button"

export { Button, buttonVariants }
