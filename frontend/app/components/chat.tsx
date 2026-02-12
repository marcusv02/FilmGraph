'use client'
import { useState } from 'react';

export default function Chat() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  const handleAsk = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });
      const data = await res.json();
      setAnswer(data.answer);
    } catch (err) {
      setAnswer("Could not connect to the Knowledge Graph.");
    }
    setLoading(false);
  };

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">FilmGraph</h1>
      <input 
        className="border p-2 w-full text-black"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask: Who did Tom Hanks work with?"
      />
      <button 
        onClick={handleAsk}
        className="bg-blue-600 text-white px-4 py-2 mt-2 rounded"
        disabled={loading}
      >
        {loading ? "Searching Graph..." : "Ask Question"}
      </button>
      {answer && <div className="mt-6 p-4 bg-gray-100 rounded text-black">{answer}</div>}
    </div>
  );
}