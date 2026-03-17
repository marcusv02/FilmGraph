"use client";
import { useEffect, useState } from "react";
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
import { Spinner } from "@/components/ui/spinner";

const suggestions = [
  "Who acted in The Dark Knight?",
  "How many times has Robert DeNiro worked with Al Pacino?",
  "Most popular genre of the 90s?",
  "List all actors who have co-starred with Christian Bale.",
  "Which directors have worked with Leonardo DiCaprio?",
  "Who's worked with Quentin Tarantino in the 21st century?",
  "Which films are longer than 3 hours?",
  "How many films were released in 1994?",
  "What is the shortest film in the database?",
  "What is the genre of Pulp Fiction?",
  "Which 70s films have a duration under 100 minutes?",
];

export default function Chat() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [sparql, setSparql] = useState("");
  const [rawAnswer, setRawAnswer] = useState([]);
  const [currentSuggestions, setCurrentSuggestions] = useState<string[]>([]);
  const [hasMounted, setHasMounted] = useState(false);

  const handleAsk = async (overrideQuestion?: string) => {
    const queryText =
      typeof overrideQuestion === "string" ? overrideQuestion : question;

    if (!queryText) return;

    setLoading(true);
    try {
      const res = await fetch(
        "https://filmgraph-production.up.railway.app/ask",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question: queryText.endsWith("?") ? queryText : queryText + "?",
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

  useEffect(() => {
    const shuffled = [...suggestions]
      .sort(() => 0.5 - Math.random())
      .slice(0, 3);

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCurrentSuggestions(shuffled);
    setHasMounted(true);
  }, []);

  if (!hasMounted) {
    return (
      <div className="py-8 px-30 w-full max-w-[60rem] mx-auto">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="py-8 px-5 md:px-30 w-full max-w-[60rem] mx-auto">
      <Field orientation="horizontal">
        <Input
        className="text-xs md:text-base"
          type="search"
          placeholder="Ask the graph a question..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && question && !loading) {
              e.preventDefault();
              handleAsk();
            }
          }}
        />
        <Button
          className="hover:cursor-pointer"
          type="submit"
          disabled={loading || !question}
          onClick={() => handleAsk()}
        >
          {loading ? (
            <Spinner />
          ) : (
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
          )}
        </Button>
      </Field>

      <Accordion
        className="mt-2"
        type="single"
        collapsible
        defaultValue="suggestions"
      >
        <AccordionItem value="suggestions">
          <AccordionTrigger>Suggestions</AccordionTrigger>
          <AccordionContent className="mt-4 flex flex-wrap gap-2 overflow-y-scroll">
            {currentSuggestions.map((text) => (
              <Button
                key={text}
                onClick={() => {
                  setQuestion(text);
                  handleAsk(text);
                }}
                size="xs"
                className="rounded-full hover:cursor-pointer hover:bg-blue-500 transition-all"
              >
                {text}
              </Button>
            ))}
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      {answer && (
        <div className="prose prose-invert max-w-none mt-4 p-4 bg-gray-50 shadow rounded-md border">
          <ReactMarkdown>{answer}</ReactMarkdown>
        </div>
      )}

      <Accordion className="mt-6" type="single" collapsible>
        <AccordionItem value="sparql" disabled={!answer}>
          <AccordionTrigger>SPARQL</AccordionTrigger>
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
