import Chat from "@/components/chat";
import Header from "@/components/header";

export default function Home() {
  return (
    <div className="flex flex-col min-h-screen items-center justify-start font-sans">
      <Header/>
      <main className="flex mt-15 w-full flex-col bg-whitek">
        <Chat/>
      </main>
    </div>
  );
}
