'use client'
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';

export default function Chat() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const [sparql, setSparql] = useState("");
  const [rawAnswer, setRawAnswer] = useState([]);

  const handleAsk = async () => {
    setLoading(true);
    try {
      const res = await fetch('https://filmgraph-production.up.railway.app/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: question.endsWith('?') ? question : question + '?' }),
      });
      const data = await res.json();
      setAnswer(data.answer);
      setSparql(data.sparql);
      setRawAnswer(data.raw_data)
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
      {/* {answer && <div className="mt-6 p-4 bg-gray-100 rounded text-black">{answer}</div>} */}
      {answer && <div className="prose prose-invert max-w-none mt-6 p-4 bg-gray-100 rounded text-black">
  <ReactMarkdown>{answer}</ReactMarkdown>
</div>}
      <div className="mt-4 text-right">
    <button 
      onClick={() => setShowRaw(!showRaw)}
      className="text-xs text-blue-500 underline uppercase tracking-widest"
    >
      {showRaw ? "Hide Technical Details" : "Show Technical Details"}
    </button>
    
    {showRaw && (
      <div className="">
        <div className="mt-2 p-3 bg-black text-green-400 text-xs font-mono rounded overflow-x-auto text-left whitespace-pre-wrap">
        <p className="mb-2 text-gray-500 border-b border-gray-800 pb-1">Generated SPARQL Query</p>
        {sparql}
      </div>
      <div className="mt-2 p-3 bg-black text-green-400 text-xs font-mono rounded overflow-x-auto text-left whitespace-pre-wrap">
        <p className="mb-2 text-gray-500 border-b border-gray-800 pb-1">Raw Answer</p>
        {/* {JSON.stringify(rawAnswer, null, 2)} */}
        {rawAnswer}
      </div>
      </div>
    )}
  </div>
    </div>
  );
}