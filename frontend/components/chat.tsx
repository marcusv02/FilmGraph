"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

export default function Chat() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [sparql, setSparql] = useState("");
  const [rawAnswer, setRawAnswer] = useState([]);

  const handleAsk = async () => {
    setLoading(true);
    try {
      const res = await fetch(
        "https://filmgraph-production.up.railway.app/ask",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question: question.endsWith("?") ? question : question + "?",
          }),
        },
      );
      const data = await res.json();
      setAnswer(data.answer);
      setSparql(data.sparql);
      setRawAnswer(data.raw_data);
    } catch (err) {
      setAnswer("Could not connect to the Knowledge Graph.");
      console.log(err);
    }
    setLoading(false);
  };

  return (
    <div className="py-8 px-30 w-full max-w-[60rem] mx-auto">
      <Field orientation="horizontal">
        <Input
          type="search"
          placeholder="Ask: Who did Tom Hanks work with?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <Button
          className="hover:cursor-pointer"
          type="submit"
          disabled={loading || !question}
          onClick={handleAsk}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="lucide lucide-send-horizontal-icon lucide-send-horizontal"
          >
            <path d="M3.714 3.048a.498.498 0 0 0-.683.627l2.843 7.627a2 2 0 0 1 0 1.396l-2.842 7.627a.498.498 0 0 0 .682.627l18-8.5a.5.5 0 0 0 0-.904z" />
            <path d="M6 12h16" />
          </svg>
        </Button>
      </Field>
      {answer && (
        <div className="prose prose-invert max-w-none mt-6 p-4 bg-gray-100 rounded text-black">
          <ReactMarkdown>{answer}</ReactMarkdown>
        </div>
      )}
      <Accordion className="border border-transparent border-t-slate-300 mt-8" type="single" collapsible defaultValue="item-1">
        <AccordionItem value="item-1">
          <AccordionTrigger>Show SPARQL</AccordionTrigger>
          <AccordionContent>
            <div className="mt-2 p-3 bg-black text-green-400 text-xs font-mono rounded overflow-x-auto text-left whitespace-pre-wrap">
              <p className="mb-2 text-gray-500 border-b border-gray-800 pb-1">
                Generated SPARQL Query
              </p>
              {sparql}
            </div>
            <div className="mt-2 p-3 bg-black text-green-400 text-xs font-mono rounded overflow-x-auto text-left whitespace-pre-wrap">
              <p className="mb-2 text-gray-500 border-b border-gray-800 pb-1">
                Generated Answer
              </p>
              {rawAnswer}
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
