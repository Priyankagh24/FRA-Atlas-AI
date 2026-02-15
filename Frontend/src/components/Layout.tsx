import { Outlet } from "react-router-dom";
import Header from "./Header";
import Chatbot from "./Chatbot";

const Layout = () => {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main>
        <Outlet />
      </main>
      <Chatbot />
    </div>
  );
};

export default Layout;