import os
import httpx
from typing import Optional
from config import settings

FMP_API_KEY = os.getenv("FMP_API_KEY", "")
FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"


async def get_income_statement(ticker: str, period: str = "quarter", limit: int = 20) -> dict:
    """
    Fetches income statement data from Financial Modeling Prep API.
    This provides ACCURATE historical financial data.
    
    Args:
        ticker: Stock symbol
        period: "quarter" or "annual"
        limit: Number of periods to fetch
        
    Returns:
        Dictionary with income statement data
    """
    try:
        if not FMP_API_KEY:
            return {
                "success": False,
                "error": "FMP_API_KEY not configured. Get free key at financialmodelingprep.com",
                "data": None
            }
        
        url = f"{FMP_BASE_URL}/income-statement/{ticker.upper()}"
        params = {
            "period": period,
            "limit": limit,
            "apikey": FMP_API_KEY
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            data = response.json()
        
        # Handle string error response
        if isinstance(data, str):
            return {
                "success": False,
                "error": f"API returned error: {data}",
                "data": None
            }
        
        # Handle dict error response
        if isinstance(data, dict) and ("Error" in data or "error" in data):
            return {
                "success": False,
                "error": data.get("Error") or data.get("error", "Unknown error"),
                "data": None
            }
        
        # Handle empty response
        if not data or not isinstance(data, list):
            return {
                "success": False,
                "error": f"No data found for {ticker}",
                "data": None
            }
        
        # Format results
        formatted = []
        for item in data:
            if not isinstance(item, dict):
                continue
                
            revenue = item.get("revenue") or 0
            gross_profit = item.get("grossProfit") or 0
            operating_income = item.get("operatingIncome") or 0
            net_income = item.get("netIncome") or 0
            
            formatted.append({
                "date": item.get("date"),
                "period": item.get("period"),
                "fiscal_year": item.get("calendarYear"),
                "revenue": revenue,
                "revenue_formatted": f"${revenue/1e9:.2f}B" if revenue else None,
                "gross_profit": gross_profit,
                "gross_profit_formatted": f"${gross_profit/1e9:.2f}B" if gross_profit else None,
                "gross_margin": f"{(gross_profit / revenue) * 100:.1f}%" if revenue else None,
                "operating_income": operating_income,
                "operating_income_formatted": f"${operating_income/1e9:.2f}B" if operating_income else None,
                "operating_margin": f"{(operating_income / revenue) * 100:.1f}%" if revenue else None,
                "net_income": net_income,
                "net_income_formatted": f"${net_income/1e9:.2f}B" if net_income else None,
                "net_margin": f"{(net_income / revenue) * 100:.1f}%" if revenue else None,
                "eps": item.get("eps"),
                "eps_diluted": item.get("epsdiluted"),
            })
        
        return {
            "success": True,
            "data": {
                "ticker": ticker.upper(),
                "period_type": period,
                "statements": formatted,
                "count": len(formatted)
            }
        }
        
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timed out. FMP API may be slow.",
            "data": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": None
        }


def get_income_statement_sync(ticker: str, period: str = "quarter", limit: int = 20) -> dict:
    """Synchronous version for LangChain tools."""
    try:
        if not FMP_API_KEY:
            return {
                "success": False,
                "error": "FMP_API_KEY not configured. Get free key at financialmodelingprep.com",
                "data": None
            }
        
        url = f"{FMP_BASE_URL}/income-statement/{ticker.upper()}"
        params = {
            "period": period,
            "limit": limit,
            "apikey": FMP_API_KEY
        }
        
        response = httpx.get(url, params=params, timeout=10.0)
        data = response.json()
        
        # Handle string error response
        if isinstance(data, str):
            return {
                "success": False,
                "error": f"API returned error: {data}",
                "data": None
            }
        
        # Handle dict error response
        if isinstance(data, dict) and ("Error" in data or "error" in data):
            return {
                "success": False,
                "error": data.get("Error") or data.get("error", "Unknown error"),
                "data": None
            }
        
        # Handle empty response
        if not data or not isinstance(data, list):
            return {
                "success": False,
                "error": f"No data found for {ticker}",
                "data": None
            }
        
        # Format results
        formatted = []
        for item in data:
            if not isinstance(item, dict):
                continue
                
            revenue = item.get("revenue") or 0
            gross_profit = item.get("grossProfit") or 0
            operating_income = item.get("operatingIncome") or 0
            net_income = item.get("netIncome") or 0
            
            formatted.append({
                "date": item.get("date"),
                "period": item.get("period"),
                "fiscal_year": item.get("calendarYear"),
                "revenue": revenue,
                "revenue_formatted": f"${revenue/1e9:.2f}B" if revenue else None,
                "gross_profit": gross_profit,
                "gross_profit_formatted": f"${gross_profit/1e9:.2f}B" if gross_profit else None,
                "gross_margin": f"{(gross_profit / revenue) * 100:.1f}%" if revenue else None,
                "operating_income": operating_income,
                "operating_income_formatted": f"${operating_income/1e9:.2f}B" if operating_income else None,
                "operating_margin": f"{(operating_income / revenue) * 100:.1f}%" if revenue else None,
                "net_income": net_income,
                "net_income_formatted": f"${net_income/1e9:.2f}B" if net_income else None,
                "net_margin": f"{(net_income / revenue) * 100:.1f}%" if revenue else None,
                "eps": item.get("eps"),
                "eps_diluted": item.get("epsdiluted"),
            })
        
        return {
            "success": True,
            "data": {
                "ticker": ticker.upper(),
                "period_type": period,
                "statements": formatted,
                "count": len(formatted)
            }
        }
        
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timed out. FMP API may be slow.",
            "data": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": None
        }


def get_quarterly_earnings(ticker: str, year: int, quarter: str) -> dict:
    """
    Gets specific quarterly earnings data.
    
    Args:
        ticker: Stock symbol
        year: Fiscal year (e.g., 2023)
        quarter: Quarter (Q1, Q2, Q3, Q4)
        
    Returns:
        Dictionary with that quarter's financial data
    """
    try:
        # Fetch all quarterly data
        result = get_income_statement_sync(ticker, "quarter", 40)
        
        # Check if request failed
        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Failed to fetch income statement"),
                "data": {
                    "ticker": ticker.upper(),
                    "requested": f"{quarter} {year}",
                    "found": False
                }
            }
        
        # Safely get statements
        data = result.get("data")
        if not data or not isinstance(data, dict):
            return {
                "success": False,
                "error": "Invalid data format received",
                "data": {
                    "ticker": ticker.upper(),
                    "requested": f"{quarter} {year}",
                    "found": False
                }
            }
        
        statements = data.get("statements")
        if not statements or not isinstance(statements, list):
            return {
                "success": False,
                "error": "No financial statements available",
                "data": {
                    "ticker": ticker.upper(),
                    "requested": f"{quarter} {year}",
                    "found": False
                }
            }
        
        # Map quarter to expected patterns
        quarter_map = {
            "Q1": ["Q1", "03-31", "03-30", "03-29", "03-28"],
            "Q2": ["Q2", "06-30", "06-29", "06-28", "06-27"],
            "Q3": ["Q3", "09-30", "09-29", "09-28", "09-27"],
            "Q4": ["Q4", "12-31", "12-30", "12-29", "12-28"]
        }
        
        target_patterns = quarter_map.get(quarter.upper(), [])
        
        # Find matching quarter
        matched = None
        for stmt in statements:
            if not isinstance(stmt, dict):
                continue
                
            stmt_year = stmt.get("fiscal_year") or (stmt.get("date", "")[:4] if stmt.get("date") else None)
            stmt_date = stmt.get("date", "") or ""
            stmt_period = stmt.get("period", "") or ""
            
            # Check year match
            if str(stmt_year) != str(year):
                continue
            
            # Check quarter match
            for pattern in target_patterns:
                if pattern in stmt_date or pattern == stmt_period:
                    matched = stmt
                    break
            
            if matched:
                break
        
        if matched:
            return {
                "success": True,
                "data": {
                    "ticker": ticker.upper(),
                    "requested": f"{quarter} {year}",
                    "found": True,
                    "financials": matched
                }
            }
        else:
            # Return available quarters for reference
            available = []
            for s in statements[:8]:
                if isinstance(s, dict):
                    period = s.get('period', '?')
                    fy = s.get('fiscal_year') or (s.get('date', '')[:4] if s.get('date') else '?')
                    available.append(f"{period} {fy}")
            
            return {
                "success": True,
                "data": {
                    "ticker": ticker.upper(),
                    "requested": f"{quarter} {year}",
                    "found": False,
                    "message": f"Could not find {quarter} {year}. This data may not be available yet. Available quarters: {', '.join(available)}",
                    "available_quarters": available
                }
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": {
                "ticker": ticker.upper(),
                "requested": f"{quarter} {year}",
                "found": False
            }
        }


def get_earnings_calendar_fmp(ticker: str) -> dict:
    """
    Gets earnings calendar from FMP.
    """
    try:
        if not FMP_API_KEY:
            return {"success": False, "error": "FMP_API_KEY not configured", "data": None}
        
        url = f"{FMP_BASE_URL}/historical/earning_calendar/{ticker.upper()}"
        params = {"apikey": FMP_API_KEY}
        
        response = httpx.get(url, params=params, timeout=10.0)
        data = response.json()
        
        # Handle error responses
        if isinstance(data, str):
            return {"success": False, "error": data, "data": None}
        
        if isinstance(data, dict) and ("Error" in data or "error" in data):
            return {"success": False, "error": data.get("Error") or data.get("error"), "data": None}
        
        if not data:
            return {"success": False, "error": "No earnings calendar data", "data": None}
        
        return {
            "success": True,
            "data": {
                "ticker": ticker.upper(),
                "earnings_dates": data[:10] if isinstance(data, list) else []
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}