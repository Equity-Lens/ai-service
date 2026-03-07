import os
import yfinance as yf
import httpx
from typing import Optional, Union
from datetime import datetime, timedelta


def get_live_market_data(ticker: str) -> dict:
    """
    Fetches real-time market data for a stock ticker.
    
    Args:
        ticker: Stock symbol (e.g., "AAPL", "MSFT", "AMD")
        
    Returns:
        Dictionary containing price, volume, P/E, and other metrics
    """
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        
        # Check if valid ticker
        if not info or info.get("regularMarketPrice") is None:
            # Try fast_info as fallback
            try:
                fast = stock.fast_info
                return {
                    "success": True,
                    "data": {
                        "symbol": ticker.upper(),
                        "current_price": round(fast.last_price, 2) if fast.last_price else None,
                        "previous_close": round(fast.previous_close, 2) if fast.previous_close else None,
                        "day_change": round(fast.last_price - fast.previous_close, 2) if fast.last_price and fast.previous_close else None,
                        "day_change_percent": round(((fast.last_price - fast.previous_close) / fast.previous_close) * 100, 2) if fast.last_price and fast.previous_close else None,
                        "market_cap": fast.market_cap,
                        "source": "yahoo_finance_fast",
                        "timestamp": datetime.now().isoformat()
                    }
                }
            except:
                return {
                    "success": False,
                    "error": f"Invalid ticker symbol: {ticker}",
                    "data": None
                }
        
        # Extract key metrics
        current_price = info.get("regularMarketPrice") or info.get("currentPrice")
        previous_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        
        # Calculate day change
        day_change = None
        day_change_percent = None
        if current_price and previous_close:
            day_change = round(current_price - previous_close, 2)
            day_change_percent = round((day_change / previous_close) * 100, 2)
        
        return {
            "success": True,
            "data": {
                "symbol": ticker.upper(),
                "company_name": info.get("shortName") or info.get("longName"),
                "current_price": round(current_price, 2) if current_price else None,
                "previous_close": round(previous_close, 2) if previous_close else None,
                "day_open": round(info.get("regularMarketOpen", 0), 2) if info.get("regularMarketOpen") else None,
                "day_high": round(info.get("dayHigh", 0), 2) if info.get("dayHigh") else None,
                "day_low": round(info.get("dayLow", 0), 2) if info.get("dayLow") else None,
                "day_change": day_change,
                "day_change_percent": day_change_percent,
                "volume": info.get("regularMarketVolume") or info.get("volume"),
                "avg_volume": info.get("averageVolume"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else None,
                "forward_pe": round(info.get("forwardPE", 0), 2) if info.get("forwardPE") else None,
                "eps": round(info.get("trailingEps", 0), 2) if info.get("trailingEps") else None,
                "dividend_yield": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
                "52_week_high": round(info.get("fiftyTwoWeekHigh", 0), 2) if info.get("fiftyTwoWeekHigh") else None,
                "52_week_low": round(info.get("fiftyTwoWeekLow", 0), 2) if info.get("fiftyTwoWeekLow") else None,
                "50_day_avg": round(info.get("fiftyDayAverage", 0), 2) if info.get("fiftyDayAverage") else None,
                "200_day_avg": round(info.get("twoHundredDayAverage", 0), 2) if info.get("twoHundredDayAverage") else None,
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "source": "yahoo_finance",
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": None
        }


def get_multiple_quotes(tickers: list[str]) -> dict:
    """
    Fetches market data for multiple tickers at once.
    
    Args:
        tickers: List of stock symbols
        
    Returns:
        Dictionary with data for each ticker
    """
    results = {}
    
    for ticker in tickers:
        results[ticker.upper()] = get_live_market_data(ticker)
    
    successful = sum(1 for r in results.values() if r["success"])
    
    return {
        "success": True,
        "data": {
            "quotes": results,
            "total_requested": len(tickers),
            "successful": successful,
            "failed": len(tickers) - successful
        }
    }


def get_price_history(ticker: str, period: str = "1mo") -> dict:
    """
    Fetches historical price data for a ticker.
    
    Args:
        ticker: Stock symbol
        period: Time period - 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        
    Returns:
        Dictionary with historical prices
    """
    try:
        stock = yf.Ticker(ticker.upper())
        history = stock.history(period=period)
        
        if history.empty:
            return {
                "success": False,
                "error": f"No historical data found for {ticker}",
                "data": None
            }
        
        # Convert to list of records
        records = []
        for date, row in history.iterrows():
            records.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"])
            })
        
        # Calculate period performance
        if len(records) >= 2:
            start_price = records[0]["close"]
            end_price = records[-1]["close"]
            period_change = round(end_price - start_price, 2)
            period_change_percent = round((period_change / start_price) * 100, 2)
        else:
            period_change = None
            period_change_percent = None
        
        return {
            "success": True,
            "data": {
                "symbol": ticker.upper(),
                "period": period,
                "data_points": len(records),
                "period_change": period_change,
                "period_change_percent": period_change_percent,
                "history": records[-30:],  # Return last 30 data points max
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": None
        }


def calculate_portfolio_value(holdings: list[dict]) -> dict:
    """
    Calculates current value of holdings using live prices.
    
    Args:
        holdings: List of {"symbol": str, "quantity": float, "avg_buy_price": float}
        
    Returns:
        Portfolio valuation with P&L
    """
    try:
        results = []
        total_invested = 0.0
        total_current_value = 0.0
        
        for holding in holdings:
            symbol = holding["symbol"]
            quantity = holding["quantity"]
            avg_price = holding["avg_buy_price"]
            
            # Get live price
            market_data = get_live_market_data(symbol)
            
            if market_data["success"] and market_data["data"]["current_price"]:
                current_price = market_data["data"]["current_price"]
                invested = quantity * avg_price
                current_value = quantity * current_price
                pnl = current_value - invested
                pnl_percent = (pnl / invested) * 100 if invested > 0 else 0
                
                results.append({
                    "symbol": symbol,
                    "quantity": quantity,
                    "avg_buy_price": avg_price,
                    "current_price": current_price,
                    "invested": round(invested, 2),
                    "current_value": round(current_value, 2),
                    "pnl": round(pnl, 2),
                    "pnl_percent": round(pnl_percent, 2),
                    "day_change": market_data["data"].get("day_change"),
                    "day_change_percent": market_data["data"].get("day_change_percent")
                })
                
                total_invested += invested
                total_current_value += current_value
            else:
                results.append({
                    "symbol": symbol,
                    "quantity": quantity,
                    "avg_buy_price": avg_price,
                    "error": f"Could not fetch price for {symbol}"
                })
        
        total_pnl = total_current_value - total_invested
        total_pnl_percent = (total_pnl / total_invested) * 100 if total_invested > 0 else 0
        
        return {
            "success": True,
            "data": {
                "holdings": results,
                "summary": {
                    "total_invested": round(total_invested, 2),
                    "total_current_value": round(total_current_value, 2),
                    "total_pnl": round(total_pnl, 2),
                    "total_pnl_percent": round(total_pnl_percent, 2)
                },
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": None
        }


def get_earnings_calendar(ticker: str) -> dict:
    """
    Fetches earnings calendar and history for a stock ticker.
    
    Args:
        ticker: Stock symbol (e.g., "SNPS", "AAPL")
        
    Returns:
        Dictionary containing upcoming and past earnings dates
    """
    try:
        stock = yf.Ticker(ticker.upper())
        
        result = {
            "symbol": ticker.upper(),
            "company_name": None,
            "next_earnings": None,
            "past_earnings": [],
            "earnings_by_quarter": {}
        }
        
        # Get company name
        try:
            info = stock.info
            result["company_name"] = info.get("shortName") or info.get("longName") or ticker.upper()
        except:
            result["company_name"] = ticker.upper()
        
        # Try to get calendar for next earnings
        try:
            calendar = stock.calendar
            if calendar is not None:
                if isinstance(calendar, dict):
                    earnings_date = calendar.get("Earnings Date")
                    if earnings_date:
                        if isinstance(earnings_date, list) and len(earnings_date) > 0:
                            result["next_earnings"] = {
                                "date": str(earnings_date[0]),
                                "date_end": str(earnings_date[1]) if len(earnings_date) > 1 else None,
                                "note": "This is the NEXT UPCOMING earnings date (future)"
                            }
                        else:
                            result["next_earnings"] = {
                                "date": str(earnings_date),
                                "note": "This is the NEXT UPCOMING earnings date (future)"
                            }
        except:
            pass
        
        # Get earnings dates history
        try:
            earnings_dates = stock.earnings_dates
            
            if earnings_dates is not None and hasattr(earnings_dates, 'empty') and not earnings_dates.empty:
                now = datetime.now()
                
                for date_idx, row in earnings_dates.head(12).iterrows():
                    try:
                        # Convert timestamp
                        if hasattr(date_idx, 'to_pydatetime'):
                            earning_date = date_idx.to_pydatetime()
                        else:
                            earning_date = date_idx
                        
                        # Determine if past or future
                        is_future = False
                        if hasattr(earning_date, 'tzinfo') and earning_date.tzinfo:
                            from datetime import timezone
                            now_tz = datetime.now(timezone.utc)
                            is_future = earning_date > now_tz
                        else:
                            try:
                                is_future = earning_date.replace(tzinfo=None) > now
                            except:
                                is_future = False
                        
                        # Format date
                        if hasattr(earning_date, 'strftime'):
                            date_str = earning_date.strftime("%B %d, %Y")
                            year = earning_date.year
                            month = earning_date.month
                        else:
                            date_str = str(earning_date)
                            year = None
                            month = None
                        
                        # Determine fiscal quarter based on month
                        fiscal_quarter = None
                        if month:
                            if month in [1, 2]:
                                fiscal_quarter = f"Q4 {year-1}"
                            elif month in [4, 5]:
                                fiscal_quarter = f"Q1 {year}"
                            elif month in [7, 8]:
                                fiscal_quarter = f"Q2 {year}"
                            elif month in [10, 11]:
                                fiscal_quarter = f"Q3 {year}"
                            else:
                                fiscal_quarter = f"Q? {year}"
                        
                        # Get EPS values
                        eps_estimate = None
                        reported_eps = None
                        surprise = None
                        
                        for col in row.index:
                            val = row[col]
                            if val is not None and str(val).lower() != 'nan':
                                try:
                                    if 'estimate' in col.lower():
                                        eps_estimate = round(float(val), 2)
                                    elif 'reported' in col.lower():
                                        reported_eps = round(float(val), 2)
                                    elif 'surprise' in col.lower():
                                        surprise = round(float(val), 2)
                                except:
                                    pass
                        
                        entry = {
                            "date": date_str,
                            "fiscal_quarter": fiscal_quarter,
                            "eps_estimate": eps_estimate,
                            "reported_eps": reported_eps,
                            "surprise_percent": surprise,
                            "status": "UPCOMING (not yet reported)" if is_future else "PAST (already reported)"
                        }
                        
                        result["past_earnings"].append(entry)
                        
                        if fiscal_quarter:
                            result["earnings_by_quarter"][fiscal_quarter] = entry
                            
                    except Exception:
                        continue
                        
        except Exception as e:
            result["earnings_history_error"] = str(e)
        
        # Create summary
        past_count = len([e for e in result["past_earnings"] if "PAST" in e.get("status", "")])
        upcoming_count = len([e for e in result["past_earnings"] if "UPCOMING" in e.get("status", "")])
        
        result["summary"] = {
            "total_earnings_dates": len(result["past_earnings"]),
            "past_earnings_count": past_count,
            "upcoming_earnings_count": upcoming_count,
            "available_quarters": list(result["earnings_by_quarter"].keys())
        }
        
        return {
            "success": True,
            "data": result,
            "instructions": "Use 'earnings_by_quarter' to find specific quarter data. 'next_earnings' shows the FUTURE date."
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": {"symbol": ticker.upper()}
        }


def get_financial_statements(ticker: str) -> dict:
    """
    Fetches actual financial statements and key metrics for a stock.
    Includes income statement, balance sheet, and cash flow data.
    
    Args:
        ticker: Stock symbol (e.g., "AMD", "AAPL")
        
    Returns:
        Dictionary containing actual financial data from SEC filings
    """
    try:
        stock = yf.Ticker(ticker.upper())
        
        result = {
            "symbol": ticker.upper(),
            "company_name": None,
            "quarterly_financials": None,
            "annual_financials": None,
            "key_metrics": None,
            "recent_quarter": None
        }
        
        # Get company name and key metrics
        try:
            info = stock.info
            result["company_name"] = info.get("shortName") or info.get("longName") or ticker.upper()
            
            result["key_metrics"] = {
                "market_cap": info.get("marketCap"),
                "enterprise_value": info.get("enterpriseValue"),
                "trailing_pe": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "peg_ratio": info.get("pegRatio"),
                "price_to_book": info.get("priceToBook"),
                "profit_margins": info.get("profitMargins"),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
                "return_on_equity": info.get("returnOnEquity"),
                "total_revenue": info.get("totalRevenue"),
                "gross_profit": info.get("grossProfits"),
                "ebitda": info.get("ebitda"),
                "total_debt": info.get("totalDebt"),
                "total_cash": info.get("totalCash"),
            }
        except Exception as e:
            result["info_error"] = str(e)
        
        # Get quarterly income statement
        try:
            quarterly_income = stock.quarterly_income_stmt
            if quarterly_income is not None and not quarterly_income.empty:
                recent_quarters = {}
                for col in quarterly_income.columns[:4]:
                    quarter_date = col.strftime("%Y-%m-%d") if hasattr(col, 'strftime') else str(col)
                    quarter_data = {}
                    
                    for idx in quarterly_income.index:
                        val = quarterly_income.loc[idx, col]
                        if val is not None and str(val).lower() != 'nan':
                            if isinstance(val, (int, float)) and abs(val) > 1000000:
                                quarter_data[str(idx)] = f"${val/1000000:,.0f}M"
                            else:
                                quarter_data[str(idx)] = val
                    
                    recent_quarters[quarter_date] = quarter_data
                
                result["quarterly_financials"] = recent_quarters
                
                # Extract most recent quarter summary
                if quarterly_income.columns.size > 0:
                    latest_col = quarterly_income.columns[0]
                    latest_date = latest_col.strftime("%Y-%m-%d") if hasattr(latest_col, 'strftime') else str(latest_col)
                    
                    def safe_get(name):
                        try:
                            val = quarterly_income.loc[name, latest_col]
                            if val is not None and str(val).lower() != 'nan':
                                return float(val)
                        except:
                            pass
                        return None
                    
                    total_revenue = safe_get("Total Revenue")
                    gross_profit = safe_get("Gross Profit")
                    operating_income = safe_get("Operating Income")
                    net_income = safe_get("Net Income")
                    
                    result["recent_quarter"] = {
                        "period": latest_date,
                        "total_revenue": f"${total_revenue/1e9:,.2f}B" if total_revenue else None,
                        "total_revenue_raw": total_revenue,
                        "gross_profit": f"${gross_profit/1e9:,.2f}B" if gross_profit else None,
                        "gross_margin": f"{(gross_profit/total_revenue)*100:.1f}%" if gross_profit and total_revenue else None,
                        "operating_income": f"${operating_income/1e9:,.2f}B" if operating_income else None,
                        "operating_margin": f"{(operating_income/total_revenue)*100:.1f}%" if operating_income and total_revenue else None,
                        "net_income": f"${net_income/1e9:,.2f}B" if net_income else None,
                        "net_margin": f"{(net_income/total_revenue)*100:.1f}%" if net_income and total_revenue else None,
                    }
        except Exception as e:
            result["quarterly_error"] = str(e)
        
        # Get earnings per share
        try:
            earnings = stock.earnings
            if earnings is not None and not earnings.empty:
                result["annual_earnings"] = earnings.tail(4).to_dict()
        except:
            pass
        
        try:
            quarterly_earnings = stock.quarterly_earnings
            if quarterly_earnings is not None and not quarterly_earnings.empty:
                result["quarterly_eps"] = quarterly_earnings.tail(4).to_dict()
        except:
            pass
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": {"symbol": ticker.upper()}
        }


def fetch_quarterly_earnings(ticker: str, year: int, quarter: str) -> dict:
    """
    Fetches quarterly earnings data for a specific quarter.
    Combines Yahoo Finance data with FMP API for comprehensive results.
    
    Args:
        ticker: Stock symbol (e.g., 'AMD', 'AAPL')
        year: Year (e.g., 2025)
        quarter: Quarter (e.g., 'Q3')
    
    Returns:
        Dict with earnings data including revenue, net income, EPS, margins
    """
    try:
        stock = yf.Ticker(ticker.upper())
        
        # Map quarter to approximate months
        quarter_map = {
            "Q1": [1, 2, 3, 4],
            "Q2": [4, 5, 6, 7],
            "Q3": [7, 8, 9, 10],
            "Q4": [10, 11, 12, 1]
        }
        target_months = quarter_map.get(quarter.upper(), [])
        
        # Try quarterly income statement first
        try:
            quarterly_income = stock.quarterly_income_stmt
            
            if quarterly_income is not None and not quarterly_income.empty:
                # Search for matching quarter
                for col in quarterly_income.columns:
                    try:
                        col_date = col.to_pydatetime() if hasattr(col, 'to_pydatetime') else col
                        col_year = col_date.year if hasattr(col_date, 'year') else None
                        col_month = col_date.month if hasattr(col_date, 'month') else None
                        
                        # Check if this column matches our target quarter
                        if col_year == year and col_month in target_months:
                            def safe_get(name):
                                try:
                                    val = quarterly_income.loc[name, col]
                                    if val is not None and str(val).lower() != 'nan':
                                        return float(val)
                                except:
                                    pass
                                return None
                            
                            revenue = safe_get("Total Revenue")
                            gross_profit = safe_get("Gross Profit")
                            operating_income = safe_get("Operating Income")
                            net_income = safe_get("Net Income")
                            
                            # Try to get EPS
                            eps = None
                            try:
                                quarterly_eps = stock.quarterly_earnings
                                if quarterly_eps is not None and not quarterly_eps.empty:
                                    for idx in quarterly_eps.index:
                                        if hasattr(idx, 'year') and idx.year == year:
                                            eps_val = quarterly_eps.loc[idx].get("Reported EPS")
                                            if eps_val is not None:
                                                eps = float(eps_val)
                                                break
                            except:
                                pass
                            
                            return {
                                "success": True,
                                "data": {
                                    "ticker": ticker.upper(),
                                    "quarter": quarter.upper(),
                                    "year": year,
                                    "date": col_date.strftime("%Y-%m-%d") if hasattr(col_date, 'strftime') else str(col_date),
                                    "revenue": revenue,
                                    "revenue_formatted": f"${revenue/1e9:.2f}B" if revenue else None,
                                    "gross_profit": gross_profit,
                                    "gross_profit_formatted": f"${gross_profit/1e9:.2f}B" if gross_profit else None,
                                    "gross_margin": f"{(gross_profit/revenue)*100:.1f}%" if gross_profit and revenue else None,
                                    "operating_income": operating_income,
                                    "operating_income_formatted": f"${operating_income/1e9:.2f}B" if operating_income else None,
                                    "operating_margin": f"{(operating_income/revenue)*100:.1f}%" if operating_income and revenue else None,
                                    "net_income": net_income,
                                    "net_income_formatted": f"${net_income/1e9:.2f}B" if net_income else None,
                                    "net_margin": f"{(net_income/revenue)*100:.1f}%" if net_income and revenue else None,
                                    "eps": eps,
                                    "source": "yahoo_finance"
                                },
                                "error": None
                            }
                    except:
                        continue
                
                # If exact quarter not found, return most recent with a note
                latest_col = quarterly_income.columns[0]
                latest_date = latest_col.to_pydatetime() if hasattr(latest_col, 'to_pydatetime') else latest_col
                
                def safe_get(name):
                    try:
                        val = quarterly_income.loc[name, latest_col]
                        if val is not None and str(val).lower() != 'nan':
                            return float(val)
                    except:
                        pass
                    return None
                
                revenue = safe_get("Total Revenue")
                gross_profit = safe_get("Gross Profit")
                operating_income = safe_get("Operating Income")
                net_income = safe_get("Net Income")
                
                actual_quarter = f"Q{((latest_date.month - 1) // 3) + 1}" if hasattr(latest_date, 'month') else "Unknown"
                actual_year = latest_date.year if hasattr(latest_date, 'year') else year
                
                return {
                    "success": True,
                    "data": {
                        "ticker": ticker.upper(),
                        "quarter": actual_quarter,
                        "year": actual_year,
                        "date": latest_date.strftime("%Y-%m-%d") if hasattr(latest_date, 'strftime') else str(latest_date),
                        "revenue": revenue,
                        "revenue_formatted": f"${revenue/1e9:.2f}B" if revenue else None,
                        "gross_profit": gross_profit,
                        "gross_profit_formatted": f"${gross_profit/1e9:.2f}B" if gross_profit else None,
                        "gross_margin": f"{(gross_profit/revenue)*100:.1f}%" if gross_profit and revenue else None,
                        "operating_income": operating_income,
                        "operating_margin": f"{(operating_income/revenue)*100:.1f}%" if operating_income and revenue else None,
                        "net_income": net_income,
                        "net_income_formatted": f"${net_income/1e9:.2f}B" if net_income else None,
                        "net_margin": f"{(net_income/revenue)*100:.1f}%" if net_income and revenue else None,
                        "source": "yahoo_finance",
                        "note": f"Exact {quarter} {year} not available. Showing latest: {actual_quarter} {actual_year}"
                    },
                    "error": None
                }
                
        except Exception as yf_error:
            pass  # Fall through to FMP
        
        # Fallback: Try FMP API if available
        FMP_API_KEY = os.getenv("FMP_API_KEY", "")
        
        if FMP_API_KEY:
            try:
                url = f"https://financialmodelingprep.com/api/v3/income-statement/{ticker}"
                params = {"period": "quarter", "limit": 8, "apikey": FMP_API_KEY}
                
                response = httpx.get(url, params=params, timeout=10.0)
                data = response.json()
                
                # Handle error responses
                if isinstance(data, str):
                    return {
                        "success": False,
                        "error": f"FMP API error: {data}",
                        "data": None
                    }
                
                if isinstance(data, dict) and ("Error Message" in data or "error" in data):
                    return {
                        "success": False,
                        "error": data.get("Error Message") or data.get("error", "Unknown API error"),
                        "data": None
                    }
                
                if isinstance(data, list) and len(data) > 0:
                    # Find matching quarter
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                            
                        item_year = item.get("calendarYear")
                        item_period = item.get("period", "")
                        
                        if str(year) == str(item_year) and quarter.upper() in item_period.upper():
                            revenue = item.get("revenue")
                            gross_profit = item.get("grossProfit")
                            operating_income = item.get("operatingIncome")
                            net_income = item.get("netIncome")
                            
                            return {
                                "success": True,
                                "data": {
                                    "ticker": ticker.upper(),
                                    "quarter": item_period,
                                    "year": item_year,
                                    "date": item.get("date"),
                                    "revenue": revenue,
                                    "revenue_formatted": f"${revenue/1e9:.2f}B" if revenue else None,
                                    "gross_profit": gross_profit,
                                    "gross_profit_formatted": f"${gross_profit/1e9:.2f}B" if gross_profit else None,
                                    "gross_margin": f"{(gross_profit/revenue)*100:.1f}%" if gross_profit and revenue else None,
                                    "operating_income": operating_income,
                                    "operating_margin": f"{(operating_income/revenue)*100:.1f}%" if operating_income and revenue else None,
                                    "net_income": net_income,
                                    "net_income_formatted": f"${net_income/1e9:.2f}B" if net_income else None,
                                    "net_margin": f"{(net_income/revenue)*100:.1f}%" if net_income and revenue else None,
                                    "eps": item.get("epsdiluted"),
                                    "source": "fmp_api"
                                },
                                "error": None
                            }
                    
                    # Return latest if no exact match
                    latest = data[0]
                    revenue = latest.get("revenue")
                    gross_profit = latest.get("grossProfit")
                    operating_income = latest.get("operatingIncome")
                    net_income = latest.get("netIncome")
                    
                    return {
                        "success": True,
                        "data": {
                            "ticker": ticker.upper(),
                            "quarter": latest.get("period", "Unknown"),
                            "year": latest.get("calendarYear"),
                            "date": latest.get("date"),
                            "revenue": revenue,
                            "revenue_formatted": f"${revenue/1e9:.2f}B" if revenue else None,
                            "gross_profit": gross_profit,
                            "operating_income": operating_income,
                            "net_income": net_income,
                            "net_income_formatted": f"${net_income/1e9:.2f}B" if net_income else None,
                            "eps": latest.get("epsdiluted"),
                            "source": "fmp_api",
                            "note": f"Exact {quarter} {year} not found. Showing latest available."
                        },
                        "error": None
                    }
                    
            except httpx.TimeoutException:
                pass  # Fall through to final fallback
            except Exception:
                pass
        
        # Final fallback: use get_financial_statements
        fallback = get_financial_statements(ticker)
        if fallback["success"]:
            fallback["data"]["note"] = f"Could not find exact {quarter} {year}. Showing latest financial data."
            fallback["data"]["requested_quarter"] = f"{quarter} {year}"
        return fallback
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": None
        }