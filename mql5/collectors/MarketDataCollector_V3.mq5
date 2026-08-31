//+------------------------------------------------------------------+
//| MarketDataCollector_V3.mq5                                       |
//| READ ONLY market data collector V3                               |
//| NO ORDER / NO TRADE FUNCTIONS                                    |
//+------------------------------------------------------------------+
#property version   "3.00"
#property strict

// -------------------------------------------------------------------
// User settings
// One identical V3 binary can be used on EZSquare and CultureCapital.
// Change only the inputs when attaching the Expert.
// -------------------------------------------------------------------
input string InpBrokerName = "EZSquare";
input string InpSymbols    = "NQ2.ez2,XAUUSD.ez2,XAGUSD.ez2,USOIL.ez2";

// -------------------------------------------------------------------
// Runtime state
// -------------------------------------------------------------------
string g_symbols[];
bool   g_symbol_enabled[];
long   g_last_tick_msc[];

string g_broker_name = "";
string g_broker_tag  = "";
string g_server      = "";
string g_company     = "";

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
string TrimText(string value)
{
   StringTrimLeft(value);
   StringTrimRight(value);
   return value;
}

bool ResolveBroker()
{
   g_broker_name = TrimText(InpBrokerName);

   if(g_broker_name == "EZSquare")
   {
      g_broker_tag = "EZ";
      return true;
   }

   if(g_broker_name == "CultureCapital")
   {
      g_broker_tag = "Culture";
      return true;
   }

   Print("MarketDataCollector V3 ERROR: InpBrokerName must be exactly ",
         "'EZSquare' or 'CultureCapital'. Current='", g_broker_name, "'");
   return false;
}

bool ParseSymbols()
{
   string raw[];
   int count = StringSplit(InpSymbols, ',', raw);

   if(count <= 0)
   {
      Print("MarketDataCollector V3 ERROR: no symbols in InpSymbols.");
      return false;
   }

   ArrayResize(g_symbols, count);
   ArrayResize(g_symbol_enabled, count);
   ArrayResize(g_last_tick_msc, count);

   int valid_count = 0;

   for(int i = 0; i < count; i++)
   {
      string symbol = TrimText(raw[i]);

      g_symbols[i] = symbol;
      g_symbol_enabled[i] = false;
      g_last_tick_msc[i] = 0;

      if(symbol == "")
      {
         Print("MarketDataCollector V3 WARNING: empty symbol entry at index ", i,
               ". This entry will be skipped.");
         continue;
      }

      if(!SymbolSelect(symbol, true))
      {
         Print("MarketDataCollector V3 WARNING: SymbolSelect FAILED: ", symbol,
               " / Error=", GetLastError(),
               ". Other symbols will continue.");
         ResetLastError();
         continue;
      }

      g_symbol_enabled[i] = true;
      valid_count++;

      Print("MarketDataCollector V3 SYMBOL OK: ", symbol);
   }

   if(valid_count <= 0)
   {
      Print("MarketDataCollector V3 ERROR: no usable symbols. Expert will stop.");
      return false;
   }

   Print("MarketDataCollector V3 SYMBOL SUMMARY: total=", count,
         " enabled=", valid_count);

   return true;
}

string CurrentPcDateYYYYMMDD()
{
   MqlDateTime dt;
   TimeToStruct(TimeLocal(), dt);

   return StringFormat("%04d%02d%02d", dt.year, dt.mon, dt.day);
}

string CurrentRawFileName()
{
   // V3 raw file rotation basis:
   // PC_TIME / TimeLocal() calendar date.
   return StringFormat("MarketDataCollector_%s_%s.csv",
                       g_broker_tag,
                       CurrentPcDateYYYYMMDD());
}

bool WriteHeaderIfNeeded(int handle)
{
   if(FileSize(handle) > 0)
      return true;

   uint written = FileWrite(
      handle,
      "PC_TIME",
      "SERVER_TIME",
      "SERVER_TIME_MSC",
      "BROKER",
      "SERVER",
      "SYMBOL",
      "BID",
      "ASK",
      "SPREAD",
      "LAST",
      "VOLUME",
      "FLAGS"
   );

   if(written <= 0)
   {
      Print("MarketDataCollector V3 ERROR: CSV header write failed. Error=",
            GetLastError());
      ResetLastError();
      return false;
   }

   return true;
}

//+------------------------------------------------------------------+
//| Initialization                                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   if(!ResolveBroker())
      return(INIT_PARAMETERS_INCORRECT);

   g_company = AccountInfoString(ACCOUNT_COMPANY);
   g_server  = AccountInfoString(ACCOUNT_SERVER);

   Print("============================================================");
   Print("MarketDataCollector V3 STARTING - READ ONLY");
   Print("BROKER=", g_broker_name);
   Print("ACCOUNT_COMPANY=", g_company);
   Print("ACCOUNT_SERVER=", g_server);
   Print("DATE_BASIS=PC_TIME(TimeLocal)");
   Print("POLLING=1 second / WRITE=new tick.time_msc only");
   Print("FILE_COMMON=YES");
   Print("============================================================");

   if(g_company == "")
      Print("MarketDataCollector V3 WARNING: ACCOUNT_COMPANY is empty.");

   if(g_server == "")
      Print("MarketDataCollector V3 WARNING: ACCOUNT_SERVER is empty.");

   if(!ParseSymbols())
      return(INIT_FAILED);

   // Confirm that the current daily file is accessible at startup.
   string file_name = CurrentRawFileName();

   int handle = FileOpen(
      file_name,
      FILE_READ | FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI,
      ','
   );

   if(handle == INVALID_HANDLE)
   {
      Print("MarketDataCollector V3 ERROR: FileOpen failed during OnInit: ",
            file_name, " / Error=", GetLastError());
      ResetLastError();
      return(INIT_FAILED);
   }

   bool header_ok = WriteHeaderIfNeeded(handle);
   FileClose(handle);

   if(!header_ok)
      return(INIT_FAILED);

   if(!EventSetTimer(1))
   {
      Print("MarketDataCollector V3 ERROR: EventSetTimer(1) failed. Error=",
            GetLastError());
      ResetLastError();
      return(INIT_FAILED);
   }

   Print("MarketDataCollector V3 STARTED: ", file_name);

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Deinitialization                                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();

   Print("MarketDataCollector V3 STOPPED. Reason=", reason,
         " / BROKER=", g_broker_name,
         " / SERVER=", g_server);
}

//+------------------------------------------------------------------+
//| No tick-driven collection                                       |
//+------------------------------------------------------------------+
void OnTick()
{
}

//+------------------------------------------------------------------+
//| 1-second polling                                                 |
//+------------------------------------------------------------------+
void OnTimer()
{
   string file_name = CurrentRawFileName();

   int handle = FileOpen(
      file_name,
      FILE_READ | FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI,
      ','
   );

   if(handle == INVALID_HANDLE)
   {
      Print("MarketDataCollector V3 ERROR: FileOpen failed: ",
            file_name, " / Error=", GetLastError());
      ResetLastError();
      return;
   }

   if(!WriteHeaderIfNeeded(handle))
   {
      FileClose(handle);
      return;
   }

   FileSeek(handle, 0, SEEK_END);

   string pc_time = TimeToString(
      TimeLocal(),
      TIME_DATE | TIME_SECONDS
   );

   for(int i = 0; i < ArraySize(g_symbols); i++)
   {
      if(!g_symbol_enabled[i])
         continue;

      MqlTick tick;

      if(!SymbolInfoTick(g_symbols[i], tick))
      {
         Print("MarketDataCollector V3 WARNING: SymbolInfoTick FAILED: ",
               g_symbols[i], " / Error=", GetLastError());
         ResetLastError();
         continue;
      }

      // New tick only. Do not delete or synthesize market ticks.
      if((long)tick.time_msc == g_last_tick_msc[i])
         continue;

      g_last_tick_msc[i] = (long)tick.time_msc;

      int digits = (int)SymbolInfoInteger(g_symbols[i], SYMBOL_DIGITS);

      double spread = tick.ask - tick.bid;

      string server_time = TimeToString(
         tick.time,
         TIME_DATE | TIME_SECONDS
      );

      uint written = FileWrite(
         handle,
         pc_time,
         server_time,
         (long)tick.time_msc,
         g_broker_name,
         g_server,
         g_symbols[i],
         DoubleToString(tick.bid, digits),
         DoubleToString(tick.ask, digits),
         DoubleToString(spread, digits),
         DoubleToString(tick.last, digits),
         (long)tick.volume,
         (long)tick.flags
      );

      if(written <= 0)
      {
         Print("MarketDataCollector V3 ERROR: FileWrite FAILED: ",
               g_symbols[i], " / File=", file_name,
               " / Error=", GetLastError());
         ResetLastError();
      }
   }

   FileFlush(handle);
   FileClose(handle);
}
//+------------------------------------------------------------------+
