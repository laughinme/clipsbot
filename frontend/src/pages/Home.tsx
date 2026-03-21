import { Header } from "@/features/navigation/ui/Header";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background flex flex-col font-sans">
      <Header />

      <main className="flex-1 p-6" />
    </div>
  )
}
