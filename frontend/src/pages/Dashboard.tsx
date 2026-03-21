import * as React from "react"
import { z } from "zod"

import data from "@/app/dashboard/data.json"
import { Header } from "@/features/navigation/ui/Header"

import { ChartAreaInteractive } from "@/shared/components/chart-area-interactive"
import { DataTable, schema } from "@/shared/components/data-table"
import { SectionCards } from "@/shared/components/section-cards"

const tableData = z.array(schema).parse(data)

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-background flex flex-col font-sans">
      <Header />
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 lg:px-6">
        <div className="@container/main flex flex-1 flex-col gap-4 py-4">
          <SectionCards />
          <div>
            <ChartAreaInteractive />
          </div>
          <DataTable data={tableData} />
        </div>
      </main>
    </div>
  )
}
