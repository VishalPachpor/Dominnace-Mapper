//+------------------------------------------------------------------+
//|                                                DominanceEA.mq5   |
//|                                  Copyright 2026, DominanceBot    |
//+------------------------------------------------------------------+
#property copyright "DominanceBot"
#property link      "https://dominancebot.com"
#property version   "1.00"

#include <Trade\Trade.mqh>

input string API_URL = "https://sorriest-mui-appliable.ngrok-free.dev";
input string EA_TOKEN = "";

CTrade trade;

// Polling intervals
int IDLE_INTERVAL = 10;
int ACTIVE_INTERVAL = 1;
int current_interval = 10;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(EA_TOKEN == "")
     {
      Print("Error: Please enter your EA Token in inputs.");
      return(INIT_FAILED);
     }
     
   Print("Dominance EA Starting...");
   Print("API Endpoint: ", API_URL);
   
   // Start with idle polling
   current_interval = IDLE_INTERVAL;
   EventSetTimer(current_interval);
   
   return(INIT_SUCCEEDED);
  }
  
//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   Print("Dominance EA Stopped.");
  }
  
//+------------------------------------------------------------------+
//| Expert timer function                                            |
//+------------------------------------------------------------------+
void OnTimer()
  {
   FetchSignals();
  }

//+------------------------------------------------------------------+
//| Polling Backend                                                  |
//+------------------------------------------------------------------+
void FetchSignals()
  {
   string cookie = NULL;
   string headers = "ea-token: " + EA_TOKEN + "\r\n";
   char post[], result[];
   string result_headers;
   
   double current_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double current_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   
   string url = API_URL + "/api/ea/signals?balance=" + DoubleToString(current_balance, 2) + "&equity=" + DoubleToString(current_equity, 2);
   
   int res = WebRequest("GET", url, headers, 5000, post, result, result_headers);
   
   bool has_signal = false;
   
   if(res == 200)
     {
      string responseStr = CharArrayToString(result);
      if(StringLen(responseStr) > 5 && StringFind(responseStr, "[]") < 0)
        {
         has_signal = true;
         ParseAndExecute(responseStr);
        }
     }
   else if(res == 401)
     {
      Print("Authentication Failed! Invalid EA Token.");
     }
   else
     {
      Print("Connection failed. Code: ", res);
     }
     
   AdjustPolling(has_signal);
  }

//+------------------------------------------------------------------+
//| Adaptive Polling Manager                                         |
//+------------------------------------------------------------------+
void AdjustPolling(bool active_signal)
  {
   int new_interval = active_signal ? ACTIVE_INTERVAL : IDLE_INTERVAL;
   
   if(new_interval != current_interval)
     {
      current_interval = new_interval;
      EventKillTimer();
      EventSetTimer(current_interval);
      Print("Adaptive Polling: Switched interval to ", current_interval, " seconds.");
     }
  }

//+------------------------------------------------------------------+
//| Very basic JSON extraction (assumes flat list of dicts)          |
//+------------------------------------------------------------------+
void ParseAndExecute(string json)
  {
   // Example JSON: [{"id":"uuid","symbol":"XAUUSD","side":"buy","lot":0.01,"sl":2330,"tp":2350}]
   
   int pos = 0;
   while((pos = StringFind(json, "{\"id\":\"", pos)) >= 0)
     {
      int end_obj = StringFind(json, "}", pos);
      if(end_obj < 0) break;
      
      string obj = StringSubstr(json, pos, end_obj - pos + 1);
      
      string trade_id = ExtractString(obj, "\"id\":\"");
      string symbol = ExtractString(obj, "\"symbol\":\"");
      string side = ExtractString(obj, "\"side\":\"");
      
      double lot = ExtractDouble(obj, "\"lot\":");
      double sl = ExtractDouble(obj, "\"sl\":");
      double tp = ExtractDouble(obj, "\"tp\":");
      
      ExecuteTrade(trade_id, symbol, side, lot, sl, tp);
      
      pos = end_obj;
     }
  }

string ExtractString(string source, string key)
  {
   int start = StringFind(source, key);
   if(start < 0) return "";
   start += StringLen(key);
   int end = StringFind(source, "\"", start);
   return StringSubstr(source, start, end - start);
  }

double ExtractDouble(string source, string key)
  {
   int start = StringFind(source, key);
   if(start < 0) return 0.0;
   start += StringLen(key);
   int end_comma = StringFind(source, ",", start);
   int end_brace = StringFind(source, "}", start);
   
   int end = end_comma;
   if(end < 0 || (end_brace > 0 && end_brace < end_comma)) end = end_brace;
   
   string val = StringSubstr(source, start, end - start);
   return StringToDouble(val);
  }

//+------------------------------------------------------------------+
//| Execute local trade and acknowledge                              |
//+------------------------------------------------------------------+
void ExecuteTrade(string trade_id, string symbol, string side, double lot, double sl, double tp)
  {
   Print("Executing target trade: ", side, " ", lot, " ", symbol);
   
   bool success = false;
   double price = 0.0;
   
   if(side == "buy")
     {
      price = SymbolInfoDouble(symbol, SYMBOL_ASK);
      success = trade.Buy(lot, symbol, price, sl, tp, "DominanceBot " + trade_id);
     }
   else if(side == "sell")
     {
      price = SymbolInfoDouble(symbol, SYMBOL_BID);
      success = trade.Sell(lot, symbol, price, sl, tp, "DominanceBot " + trade_id);
     }
     
   if(success)
     {
      Print("Trade executed successfully!");
      ConfirmTrade(trade_id, "executed", price);
     }
   else
     {
      Print("Trade execution failed. Code: ", trade.ResultRetcode());
      ConfirmTrade(trade_id, "failed", 0);
     }
  }

//+------------------------------------------------------------------+
//| Acknowledge to Backend                                           |
//+------------------------------------------------------------------+
void ConfirmTrade(string trade_id, string statusStr, double price)
  {
   string url = API_URL + "/api/ea/confirm";
   string headers = "ea-token: " + EA_TOKEN + "\r\nContent-Type: application/json\r\n";
   
   string payload = "{\"trade_id\":\"" + trade_id + "\",\"status\":\"" + statusStr + "\",\"price\":" + DoubleToString(price) + "}";
   
   char post[];
   StringToCharArray(payload, post);
   ArrayResize(post, ArraySize(post)-1); // Remove null terminator
   
   char result[];
   string result_headers;
   
   int res = WebRequest("POST", url, headers, 5000, post, result, result_headers);
   if(res == 200)
     {
      Print("Confirmed trade ", trade_id, " status: ", statusStr, " with server.");
     }
   else
     {
      Print("Failed to confirm trade with server. Code: ", res);
     }
  }
//+------------------------------------------------------------------+
