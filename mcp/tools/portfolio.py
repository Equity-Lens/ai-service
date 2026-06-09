import asyncpg
from typing import Optional
from config import settings


async def get_db_connection():
    """
    Creates a connection to PostgreSQL database.
    """
    return await asyncpg.connect(settings.DATABASE_URL)


async def get_user_holdings(user_id: int) -> dict:
    """
    Fetches all stock holdings for a user across all their portfolios.
    """
    conn = None
    try:
        conn = await get_db_connection()
        
        portfolios = await conn.fetch(
            """
            SELECT id, name, broker, description, is_default
            FROM portfolios
            WHERE user_id = $1
            ORDER BY is_default DESC, name ASC
            """,
            user_id
        )
        
        if not portfolios:
            return {
                "success": True,
                "data": {
                    "portfolios": [],
                    "total_holdings": 0,
                    "portfolios_count": 0,
                    "message": "No portfolios found for this user"
                }
            }
        
        result = []
        total_holdings = 0
        
        for portfolio in portfolios:
            holdings = await conn.fetch(
                """
                SELECT 
                    symbol,
                    quantity,
                    avg_buy_price,
                    notes,
                    added_at
                FROM portfolio_holdings
                WHERE portfolio_id = $1
                ORDER BY symbol ASC
                """,
                portfolio["id"]
            )
            
            holdings_list = [
                {
                    "symbol": h["symbol"],
                    "quantity": float(h["quantity"]),
                    "avg_buy_price": float(h["avg_buy_price"]),
                    "notes": h["notes"],
                    "added_at": h["added_at"].isoformat() if h["added_at"] else None
                }
                for h in holdings
            ]
            
            total_holdings += len(holdings_list)
            
            result.append({
                "portfolio_id": portfolio["id"],
                "name": portfolio["name"],
                "broker": portfolio["broker"],
                "description": portfolio["description"],
                "is_default": portfolio["is_default"],
                "holdings": holdings_list,
                "holdings_count": len(holdings_list)
            })
        
        return {
            "success": True,
            "data": {
                "portfolios": result,
                "total_holdings": total_holdings,
                "portfolios_count": len(result)
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": None
        }
    finally:
        if conn:
            await conn.close()


async def get_user_alerts(user_id: int) -> dict:
    """
    Fetches all price alerts for a user.
    """
    conn = None
    try:
        conn = await get_db_connection()
        
        alerts = await conn.fetch(
            """
            SELECT 
                id,
                symbol,
                alert_type,
                target_value,
                base_price,
                is_active,
                is_triggered
            FROM price_alerts
            WHERE user_id = $1
            ORDER BY is_active DESC, symbol ASC
            """,
            user_id
        )
        
        if not alerts:
            return {
                "success": True,
                "data": {
                    "alerts": [],
                    "total_alerts": 0,
                    "active_alerts": 0,      # ✅ consistent keys always present
                    "triggered_alerts": 0,
                    "message": "No price alerts found for this user"
                }
            }
        
        alerts_list = [
            {
                "id": a["id"],
                "symbol": a["symbol"],
                "alert_type": a["alert_type"],
                "target_value": float(a["target_value"]) if a["target_value"] else None,
                "base_price": float(a["base_price"]) if a["base_price"] else None,
                "is_active": a["is_active"],
                "is_triggered": a["is_triggered"]
            }
            for a in alerts
        ]
        
        active_count = sum(1 for a in alerts_list if a["is_active"])
        triggered_count = sum(1 for a in alerts_list if a["is_triggered"])
        
        return {
            "success": True,
            "data": {
                "alerts": alerts_list,
                "total_alerts": len(alerts_list),
                "active_alerts": active_count,
                "triggered_alerts": triggered_count
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": None
        }
    finally:
        if conn:
            await conn.close()


async def get_portfolio_summary(user_id: int) -> dict:
    """
    Gets a summary of user's portfolio for AI context.
    Combines holdings with basic stats.
    """
    holdings_result = await get_user_holdings(user_id)
    alerts_result = await get_user_alerts(user_id)
    
    if not holdings_result["success"]:
        return holdings_result
    
    all_symbols = set()
    total_invested = 0.0
    
    for portfolio in holdings_result["data"]["portfolios"]:
        for holding in portfolio["holdings"]:
            all_symbols.add(holding["symbol"])
            total_invested += holding["quantity"] * holding["avg_buy_price"]
    
    return {
        "success": True,
        "data": {
            "symbols_owned": list(all_symbols),
            "total_positions": holdings_result["data"]["total_holdings"],
            "total_invested": round(total_invested, 2),
            "portfolios_count": holdings_result["data"]["portfolios_count"],
            "active_alerts": alerts_result["data"]["active_alerts"] if alerts_result["success"] else 0,
            "portfolios": holdings_result["data"]["portfolios"],
            "alerts": alerts_result["data"]["alerts"] if alerts_result["success"] else []
        }
    }