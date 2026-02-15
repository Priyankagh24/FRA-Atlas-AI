import React, { useState, useRef, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;
import {
  MessageCircle,
  Send,
  X,
  Minimize2,
  Maximize2,
  User,
  Bot,
  HelpCircle,
  FileText,
  Map,
  Users
} from "lucide-react";

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'bot';
  timestamp: Date;
  type?: 'text' | 'suggestion' | 'data';
}

const Chatbot = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: 'Hello! I\'m your FRA Atlas assistant. I can help you with Forest Rights Act processes, data queries, and scheme recommendations. What would you like to know?',
      sender: 'bot',
      timestamp: new Date(),
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const quickActions = [
    { icon: HelpCircle, text: 'FRA Process Help', action: 'fra-help' },
    { icon: FileText, text: 'Check Claim Status', action: 'claim-status' },
    { icon: Map, text: 'Find Village Data', action: 'village-data' },
    { icon: Users, text: 'Scheme Recommendations', action: 'schemes' },
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (text?: string, action?: string) => {
    const messageText = text || inputValue.trim();
    if (!messageText) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: messageText,
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsTyping(true);

    try {
      const response = await fetch(
        `${BACKEND_URL}/dss/check?q=${encodeURIComponent(messageText)}`,
        { method: "GET" }
      );

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      let data;
      const contentType = response.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        const json = await response.json();
        data = JSON.stringify(json);
      } else {
        data = await response.text();
      }

      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: data,
        sender: 'bot',
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error(error);
      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: "❌ Sorry, I couldn't reach the server. Please check if the backend is running at http://127.0.0.1:8000/dss/check",
        sender: 'bot',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, botMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleInputKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const tryParseJSON = (text: string) => {
    try {
      return JSON.parse(text);
    } catch {
      return null;
    }
  };

  if (!isOpen) {
    return (
      <div className="fixed bottom-4 right-4 z-[9999] mb-2">
        <Button
          onClick={() => setIsOpen(true)}
          size="lg"
          className="rounded-full h-14 w-14 shadow-interactive animate-pulse-glow"
          variant="hero"
        >
          <MessageCircle className="h-6 w-6" />
        </Button>
      </div>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 z-[9999]">
      <Card className={`w-96 shadow-elevated transition-all duration-300 ${isMinimized ? 'h-16' : 'h-[500px]'
        }`}>
        {/* Header */}
        <CardHeader className="pb-3 border-b">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-accent rounded-full flex items-center justify-center">
                <Bot className="h-4 w-4 text-accent-foreground" />
              </div>
              <div>
                <CardTitle className="text-sm">FRA Assistant</CardTitle>
                <CardDescription className="text-xs">Always here to help</CardDescription>
              </div>
            </div>
            <div className="flex space-x-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsMinimized(!isMinimized)}
              >
                {isMinimized ? (
                  <Maximize2 className="h-4 w-4" />
                ) : (
                  <Minimize2 className="h-4 w-4" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsOpen(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardHeader>

        {!isMinimized && (
          <>
            {/* Messages */}
            <CardContent className="h-80 overflow-y-auto p-4 space-y-4">
              {messages.map((message) => {
                const parsed = tryParseJSON(message.text);
                let finalResults = parsed?.results || [];

if (parsed?.results) {
  const grouped: any = {};

  parsed.results.forEach((r: any) => {
    // 👇 KEY FIX: separate people even if claim_id is same
    const key = `${r.claim_id}-${r.patta_holder_name}`;
    grouped[key] = r;
  });

  finalResults = Object.values(grouped);
}

                return (
                  <div
                    key={message.id}
                    className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`flex items-start space-x-2 max-w-[80%] ${message.sender === 'user' ? 'flex-row-reverse space-x-reverse' : ''
                        }`}
                    >
                      <div className={`w-6 h-6 rounded-full flex items-center justify-center ${message.sender === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-muted-foreground'
                        }`}>
                        {message.sender === 'user' ? <User className="h-3 w-3" /> : <Bot className="h-3 w-3" />}
                      </div>
                      <div
                        className={`rounded-lg px-3 py-2 text-sm ${message.sender === 'user'
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted text-muted-foreground'
                          }`}
                      >
                        {parsed && parsed.results ? (
                          <div className="space-y-2">
                            <p className="font-semibold text-accent">
                              📑 Scheme: {parsed.scheme || "N/A"} ({parsed.count} records)
                            </p>

                            <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                              {finalResults.map((person: any, idx: number) => (

                                <div
                                  key={idx}
                                  className="border rounded-md p-2 bg-background text-xs shadow-sm"
                                >
                                  <p className="font-semibold">
                                    👤 {person.patta_holder_name || "Unknown"} ({person.gender}, {person.age} yrs)
                                  </p>
                                  <p>👨‍👩 Father/Husband: {person.father_or_husband_name}</p>
                                  <p>🏡 Address: {person.address}</p>
                                  <p>
                                    📍 {person.village_name}, {person.block}, {person.district}, {person.state}
                                  </p>
                                  <p>🌱 Land Use: {person.land_use} ({person.total_area_claimed})</p>
                                  <p>📌 Coordinates: {person.coordinates}</p>
                                  <p>🆔 Claim ID: {person.claim_id} | Survey: {person.survey_number}</p>
                                  <p>🌳 Forest Cover: {person.forest_cover} | 💧 Water: {person.water_bodies}</p>
                                  <p>🏠 Homestead: {person.homestead}</p>
                                  <p>👨‍👩‍👧 Family Size: {person.family_size}</p>
                                  <p>📞 {person.phone} | Aadhaar: {person.aadhaar}</p>
                                  <p>🗓️ Applied: {person.date_of_application} | Verified: {person.verification_date}</p>
                                  <p>📄 Status: {person.status} ({person.type})</p>

                                  {person.schemes?.length > 0 && (
                                    <p>✅ Schemes: {person.schemes.join(", ")}</p>
                                  )}
                                  {person.documents?.length > 0 && (
                                    <p>📂 Documents: {person.documents.join(", ")}</p>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <p className="whitespace-pre-wrap">{message.text}</p>
                        )}

                        <p className="text-xs opacity-70 mt-1">
                          {message.timestamp.toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}

              {isTyping && (
                <div className="flex justify-start">
                  <div className="flex items-center space-x-2">
                    <div className="w-6 h-6 bg-muted rounded-full flex items-center justify-center">
                      <Bot className="h-3 w-3" />
                    </div>
                    <div className="bg-muted rounded-lg px-3 py-2">
                      <div className="flex space-x-1">
                        <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
                        <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce delay-100" />
                        <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce delay-200" />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </CardContent>

            {/* Input */}
            <div className="border-t p-3">
              <div className="flex items-center space-x-2">
                <Input
                  ref={inputRef}
                  placeholder="Ask about FRA processes, claims, or schemes..."
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleInputKeyPress}
                  className="flex-1 h-10"
                />
                <Button
                  onClick={() => handleSendMessage()}
                  disabled={!inputValue.trim() || isTyping}
                  size="sm"
                  className="h-10 w-10 flex items-center justify-center"
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  );
};

export default Chatbot;
