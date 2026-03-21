import { BrowserRouter } from "react-router-dom";
import { useAuth } from "@/app/providers/auth/useAuth";
import { AppRoutes } from "@/app/routes/AppRoutes";

function App() {
  const authData = useAuth();

  if (!authData) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-red-100">
        <div className="p-8 bg-white rounded-lg shadow-md text-center">
          <h1 className="text-2xl font-bold text-red-600 mb-2">Ошибка конфигурации</h1>
        </div>
      </div>
    );
  }

  const {
    isUserLoading,
    isRestoringSession
  } = authData;

  if (isRestoringSession) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-lg text-slate-500">Загрузка сессии...</p>
      </div>
    );
  }

  if (isUserLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-lg text-slate-500">Загрузка пользователя...</p>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}

export default App;
