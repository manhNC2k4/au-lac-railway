"use client";

import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";

export const Tabs = TabsPrimitive.Root;

export const TabsList = forwardRef<
  ElementRef<typeof TabsPrimitive.List>,
  ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(function TabsList({ className, ...props }, ref) {
  return (
    <TabsPrimitive.List
      ref={ref}
      className={cn("inline-flex items-center gap-1 rounded-xl bg-surface p-1", className)}
      {...props}
    />
  );
});

export const TabsTrigger = forwardRef<
  ElementRef<typeof TabsPrimitive.Trigger>,
  ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(function TabsTrigger({ className, ...props }, ref) {
  return (
    <TabsPrimitive.Trigger
      ref={ref}
      className={cn(
        "min-h-[38px] rounded-lg px-4 text-sm font-medium text-muted transition-colors",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary",
        "data-[state=active]:bg-white data-[state=active]:text-primary data-[state=active]:shadow-card",
        className,
      )}
      {...props}
    />
  );
});

export const TabsContent = TabsPrimitive.Content;
