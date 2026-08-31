//+------------------------------------------------------------------+
//| MACD_Trend_Arrow_Signals_v22.mq5                                |
//| MACD + 5-factor score: MA / Ichi / Cloud / Momentum / ATR       |
//| SIGNAL ONLY - NO AUTO TRADING                                   |
//+------------------------------------------------------------------+
#property version   "2.20"
#property strict
#property indicator_chart_window

#property indicator_buffers 6
#property indicator_plots   6

//--- WATCH BUY (score 0-3)
#property indicator_label1  "WATCH BUY"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrLimeGreen
#property indicator_width1  1
//--- WATCH SELL (score 0-3)
#property indicator_label2  "WATCH SELL"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrTomato
#property indicator_width2  1
//--- CONFIRMED BUY (score 4)
#property indicator_label3  "CONFIRMED BUY"
#property indicator_type3   DRAW_ARROW
#property indicator_color3  clrBlue
#property indicator_width3  3
//--- CONFIRMED SELL (score 4)
#property indicator_label4  "CONFIRMED SELL"
#property indicator_type4   DRAW_ARROW
#property indicator_color4  clrMagenta
#property indicator_width4  3
//--- STRONG BUY (score 5)
#property indicator_label5  "STRONG BUY"
#property indicator_type5   DRAW_ARROW
#property indicator_color5  clrRed
#property indicator_width5  5
//--- STRONG SELL (score 5)
#property indicator_label6  "STRONG SELL"
#property indicator_type6   DRAW_ARROW
#property indicator_color6  clrLimeGreen
#property indicator_width6  5

input int MACD_Fast=12;
input int MACD_Slow=26;
input int MACD_Signal=9;
input int MA_Fast=30;
input int MA_Slow=60;
input int Tenkan=9;
input int Kijun=26;
input int SenkouB=52;
input int ATR_Period=14;
input double Min_MACD_ATR_Ratio=0.03;

// CSV auto logging: only newly closed-bar signals, with duplicate prevention
input bool Enable_CSV_Log=true;
input string CSV_FilePrefix="MACD_Trend_Arrow_Signals_v22";

// Buffers
double WatchBuyBuffer[], WatchSellBuffer[];
double ConfirmedBuyBuffer[], ConfirmedSellBuffer[];
double StrongBuyBuffer[], StrongSellBuffer[];

// Handles
int MACDHandle=INVALID_HANDLE, MA30Handle=INVALID_HANDLE, MA60Handle=INVALID_HANDLE;
int IchimokuHandle=INVALID_HANDLE, ATRHandle=INVALID_HANDLE;
datetime LastLoggedBarTime=0;

string PeriodText()
{
   return(EnumToString((ENUM_TIMEFRAMES)_Period));
}

string SafeFilePart(string s)
{
   StringReplace(s,"\\","_");
   StringReplace(s,"/","_");
   StringReplace(s,":","_");
   StringReplace(s,"*","_");
   StringReplace(s,"?","_");
   StringReplace(s,"\"","_");
   StringReplace(s,"<","_");
   StringReplace(s,">","_");
   StringReplace(s,"|","_");
   StringReplace(s," ","_");
   return(s);
}

string BrokerTag()
{
   string server=AccountInfoString(ACCOUNT_SERVER);
   string company=AccountInfoString(ACCOUNT_COMPANY);
   string probe=server+" "+company;
   StringToLower(probe);

   if(StringFind(probe,"ezsquare")>=0 || StringFind(probe,"ez square")>=0)
      return("EZSquare");
   if(StringFind(probe,"culturecapital")>=0 || StringFind(probe,"culture capital")>=0)
      return("CultureCapital");

   if(server!="") return(SafeFilePart(server));
   if(company!="") return(SafeFilePart(company));
   return("Other");
}

string BrokerCSVFileName()
{
   return(CSV_FilePrefix+"_"+BrokerTag()+".csv");
}

bool EnsureCSVFile()
{
   if(!Enable_CSV_Log) return(true);

   string file_name=BrokerCSVFileName();
   int h=FileOpen(file_name,FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI,';');
   if(h==INVALID_HANDLE)
   {
      Print("V2.2 CSV init/open error: ",GetLastError()," file=",file_name);
      return(false);
   }

   if(FileSize(h)==0)
      FileWrite(h,"TIME","BROKER","SERVER","SYMBOL","PERIOD","DIRECTION","SCORE","CLASS","PRICE",
                  "MA","ICHI","CLOUD","MOMENTUM","MACD_ATR","MACD_ATR_RATIO");

   FileFlush(h);
   FileClose(h);
   return(true);
}

void LogSignal(datetime bar_time,string direction,int score,string signal_class,double price,
               bool ma_ok,bool ichi_ok,bool cloud_ok,bool momentum_ok,bool atr_ok,double ratio)
{
   if(!Enable_CSV_Log) return;

   string file_name=BrokerCSVFileName();
   int h=FileOpen(file_name,FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI,';');
   if(h==INVALID_HANDLE){ Print("V2.2 CSV open error: ",GetLastError()," file=",file_name); return; }

   if(FileSize(h)==0)
      FileWrite(h,"TIME","BROKER","SERVER","SYMBOL","PERIOD","DIRECTION","SCORE","CLASS","PRICE",
                  "MA","ICHI","CLOUD","MOMENTUM","MACD_ATR","MACD_ATR_RATIO");

   FileSeek(h,0,SEEK_END);
   FileWrite(h,TimeToString(bar_time,TIME_DATE|TIME_MINUTES),BrokerTag(),
             AccountInfoString(ACCOUNT_SERVER),_Symbol,PeriodText(),direction,score,
             signal_class,DoubleToString(price,_Digits),(int)ma_ok,(int)ichi_ok,(int)cloud_ok,
             (int)momentum_ok,(int)atr_ok,DoubleToString(ratio,6));
   FileFlush(h); FileClose(h);
}

int OnInit()
{
   SetIndexBuffer(0,WatchBuyBuffer,INDICATOR_DATA);
   SetIndexBuffer(1,WatchSellBuffer,INDICATOR_DATA);
   SetIndexBuffer(2,ConfirmedBuyBuffer,INDICATOR_DATA);
   SetIndexBuffer(3,ConfirmedSellBuffer,INDICATOR_DATA);
   SetIndexBuffer(4,StrongBuyBuffer,INDICATOR_DATA);
   SetIndexBuffer(5,StrongSellBuffer,INDICATOR_DATA);
   ArraySetAsSeries(WatchBuyBuffer,true); ArraySetAsSeries(WatchSellBuffer,true);
   ArraySetAsSeries(ConfirmedBuyBuffer,true); ArraySetAsSeries(ConfirmedSellBuffer,true);
   ArraySetAsSeries(StrongBuyBuffer,true); ArraySetAsSeries(StrongSellBuffer,true);

   PlotIndexSetInteger(0,PLOT_ARROW,233); // WATCH BUY
   PlotIndexSetInteger(1,PLOT_ARROW,234); // WATCH SELL
   PlotIndexSetInteger(2,PLOT_ARROW,233); // CONFIRMED BUY
   PlotIndexSetInteger(3,PLOT_ARROW,234); // CONFIRMED SELL
   PlotIndexSetInteger(4,PLOT_ARROW,171); // STRONG BUY circle
   PlotIndexSetInteger(5,PLOT_ARROW,171); // STRONG SELL circle
   for(int p=0;p<6;p++) PlotIndexSetDouble(p,PLOT_EMPTY_VALUE,EMPTY_VALUE);

   MACDHandle=iMACD(_Symbol,_Period,MACD_Fast,MACD_Slow,MACD_Signal,PRICE_CLOSE);
   MA30Handle=iMA(_Symbol,_Period,MA_Fast,0,MODE_SMA,PRICE_CLOSE);
   MA60Handle=iMA(_Symbol,_Period,MA_Slow,0,MODE_SMA,PRICE_CLOSE);
   IchimokuHandle=iIchimoku(_Symbol,_Period,Tenkan,Kijun,SenkouB);
   ATRHandle=iATR(_Symbol,_Period,ATR_Period);
   if(MACDHandle==INVALID_HANDLE || MA30Handle==INVALID_HANDLE || MA60Handle==INVALID_HANDLE ||
      IchimokuHandle==INVALID_HANDLE || ATRHandle==INVALID_HANDLE)
   { Print("V2.2 indicator handle creation failed. Error=",GetLastError()); return(INIT_FAILED); }

   IndicatorSetString(INDICATOR_SHORTNAME,"MACD Trend Arrows V2.2 Score");

   // Create the broker-separated CSV immediately when the indicator is loaded.
   EnsureCSVFile();

   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(MACDHandle!=INVALID_HANDLE) IndicatorRelease(MACDHandle);
   if(MA30Handle!=INVALID_HANDLE) IndicatorRelease(MA30Handle);
   if(MA60Handle!=INVALID_HANDLE) IndicatorRelease(MA60Handle);
   if(IchimokuHandle!=INVALID_HANDLE) IndicatorRelease(IchimokuHandle);
   if(ATRHandle!=INVALID_HANDLE) IndicatorRelease(ATRHandle);
}

int OnCalculate(const int rates_total,const int prev_calculated,const datetime &time[],
 const double &open[],const double &high[],const double &low[],const double &close[],
 const long &tick_volume[],const long &volume[],const int &spread[])
{
   if(rates_total<150) return(0);
   ArraySetAsSeries(time,true); ArraySetAsSeries(high,true); ArraySetAsSeries(low,true); ArraySetAsSeries(close,true);

   double MACDMain[],MACDSignalLine[],MA30[],MA60[],TenkanLine[],KijunLine[],SpanA[],SpanB[],ATR[];
   ArraySetAsSeries(MACDMain,true); ArraySetAsSeries(MACDSignalLine,true);
   ArraySetAsSeries(MA30,true); ArraySetAsSeries(MA60,true); ArraySetAsSeries(TenkanLine,true);
   ArraySetAsSeries(KijunLine,true); ArraySetAsSeries(SpanA,true); ArraySetAsSeries(SpanB,true); ArraySetAsSeries(ATR,true);

   int c1=CopyBuffer(MACDHandle,0,0,rates_total,MACDMain);
   int c2=CopyBuffer(MACDHandle,1,0,rates_total,MACDSignalLine);
   int c3=CopyBuffer(MA30Handle,0,0,rates_total,MA30);
   int c4=CopyBuffer(MA60Handle,0,0,rates_total,MA60);
   int c5=CopyBuffer(IchimokuHandle,0,0,rates_total,TenkanLine);
   int c6=CopyBuffer(IchimokuHandle,1,0,rates_total,KijunLine);
   int c7=CopyBuffer(IchimokuHandle,2,-Kijun,rates_total,SpanA);
   int c8=CopyBuffer(IchimokuHandle,3,-Kijun,rates_total,SpanB);
   int c9=CopyBuffer(ATRHandle,0,0,rates_total,ATR);
   if(c1<=0||c2<=0||c3<=0||c4<=0||c5<=0||c6<=0||c7<=0||c8<=0||c9<=0) return(prev_calculated);

   int available=c1;
   available=MathMin(available,c2); available=MathMin(available,c3); available=MathMin(available,c4);
   available=MathMin(available,c5); available=MathMin(available,c6); available=MathMin(available,c7);
   available=MathMin(available,c8); available=MathMin(available,c9);

   for(int i=available-1;i>=0;i--)
   { WatchBuyBuffer[i]=EMPTY_VALUE; WatchSellBuffer[i]=EMPTY_VALUE; ConfirmedBuyBuffer[i]=EMPTY_VALUE;
     ConfirmedSellBuffer[i]=EMPTY_VALUE; StrongBuyBuffer[i]=EMPTY_VALUE; StrongSellBuffer[i]=EMPTY_VALUE; }

   for(int i=available-2;i>=1;i--)
   {
      double candle_range=high[i]-low[i];
      double normal_offset=MathMax(candle_range*0.25,20*_Point);
      double confirmed_offset=MathMax(candle_range*0.40,30*_Point);
      double strong_offset=MathMax(candle_range*0.55,40*_Point);

      bool MACD_Buy=(MACDMain[i]>MACDSignalLine[i] && MACDMain[i+1]<=MACDSignalLine[i+1]);
      bool MACD_Sell=(MACDMain[i]<MACDSignalLine[i] && MACDMain[i+1]>=MACDSignalLine[i+1]);
      if(!MACD_Buy && !MACD_Sell) continue;

      double HistNow=MACDMain[i]-MACDSignalLine[i];
      double HistPrev=MACDMain[i+1]-MACDSignalLine[i+1];
      bool Momentum_Bull=(HistNow>HistPrev), Momentum_Bear=(HistNow<HistPrev);
      bool MA_Bull=(close[i]>MA30[i] && MA30[i]>MA60[i]);
      bool MA_Bear=(close[i]<MA30[i] && MA30[i]<MA60[i]);
      bool Ichi_Bull=(TenkanLine[i]>KijunLine[i] && close[i]>KijunLine[i]);
      bool Ichi_Bear=(TenkanLine[i]<KijunLine[i] && close[i]<KijunLine[i]);
      double CloudTop=MathMax(SpanA[i],SpanB[i]), CloudBottom=MathMin(SpanA[i],SpanB[i]);
      bool AboveCloud=(close[i]>CloudTop), BelowCloud=(close[i]<CloudBottom);
      double ratio=0.0; bool MACD_StrongEnough=false;
      if(ATR[i]>0){ ratio=MathAbs(MACDMain[i])/ATR[i]; MACD_StrongEnough=(ratio>=Min_MACD_ATR_Ratio); }

      int score=0; bool ma_ok=false,ichi_ok=false,cloud_ok=false,momentum_ok=false;
      string direction=""; double signal_price=close[i];
      if(MACD_Buy)
      {
         direction="BUY"; ma_ok=MA_Bull; ichi_ok=Ichi_Bull; cloud_ok=AboveCloud; momentum_ok=Momentum_Bull;
         score=(int)ma_ok+(int)ichi_ok+(int)cloud_ok+(int)momentum_ok+(int)MACD_StrongEnough;
         if(score==5) StrongBuyBuffer[i]=low[i]-strong_offset;
         else if(score==4) ConfirmedBuyBuffer[i]=low[i]-confirmed_offset;
         else WatchBuyBuffer[i]=low[i]-normal_offset;
      }
      else
      {
         direction="SELL"; ma_ok=MA_Bear; ichi_ok=Ichi_Bear; cloud_ok=BelowCloud; momentum_ok=Momentum_Bear;
         score=(int)ma_ok+(int)ichi_ok+(int)cloud_ok+(int)momentum_ok+(int)MACD_StrongEnough;
         if(score==5) StrongSellBuffer[i]=high[i]+strong_offset;
         else if(score==4) ConfirmedSellBuffer[i]=high[i]+confirmed_offset;
         else WatchSellBuffer[i]=high[i]+normal_offset;
      }

      // Log only the newest completed bar, once. Historical recalculation is not duplicated into CSV.
      if(i==1 && time[i]!=LastLoggedBarTime)
      {
         string cls=(score==5 ? "STRONG" : (score==4 ? "CONFIRMED" : "WATCH"));
         LogSignal(time[i],direction,score,cls,signal_price,ma_ok,ichi_ok,cloud_ok,momentum_ok,MACD_StrongEnough,ratio);
         LastLoggedBarTime=time[i];
      }
   }
   return(rates_total);
}
//+------------------------------------------------------------------+
