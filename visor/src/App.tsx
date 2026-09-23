import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Salud } from "@/components/Salud"
import { Decisiones } from "@/components/Decisiones"
import { Aprobaciones } from "@/components/Aprobaciones"
import { Trazas } from "@/components/Trazas"

export default function App() {
  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-xl font-bold mb-4">Tablero MDR</h1>
      <Tabs defaultValue="salud">
        <TabsList>
          <TabsTrigger value="salud">Salud</TabsTrigger>
          <TabsTrigger value="decisiones">Decisiones</TabsTrigger>
          <TabsTrigger value="aprobaciones">Aprobaciones</TabsTrigger>
          <TabsTrigger value="trazas">Trazas</TabsTrigger>
        </TabsList>
        <TabsContent value="salud"><Salud /></TabsContent>
        <TabsContent value="decisiones"><Decisiones /></TabsContent>
        <TabsContent value="aprobaciones"><Aprobaciones /></TabsContent>
        <TabsContent value="trazas"><Trazas /></TabsContent>
      </Tabs>
    </div>
  )
}
