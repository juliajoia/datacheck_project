import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center gap-4 py-24 text-center">
      <p className="text-6xl font-bold text-primary">404</p>
      <p className="text-muted-foreground">Esta página não existe.</p>
      <Button asChild><Link to="/">Voltar ao Dashboard</Link></Button>
    </div>
  );
}
