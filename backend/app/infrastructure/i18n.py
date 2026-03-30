"""
Internationalization (i18n) support for multi-language functionality.
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache

logger = logging.getLogger(__name__)


class Language(Enum):
    """Supported languages."""
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    JAPANESE = "ja"
    CHINESE = "zh"
    PORTUGUESE = "pt"
    RUSSIAN = "ru"
    ARABIC = "ar"
    ITALIAN = "it"


class TranslationKey(Enum):
    """Translation keys for different UI elements."""
    # Navigation
    DASHBOARD = "dashboard"
    PORTFOLIO = "portfolio"
    TRADING = "trading"
    ANALYTICS = "analytics"
    SETTINGS = "settings"
    LOGOUT = "logout"
    
    # Trading
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    MARKET_ORDER = "market_order"
    LIMIT_ORDER = "limit_order"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    
    # Portfolio
    TOTAL_VALUE = "total_value"
    TOTAL_PNL = "total_pnl"
    PNL_PERCENTAGE = "pnl_percentage"
    POSITIONS = "positions"
    ASSETS = "assets"
    CASH = "cash"
    
    # Risk
    RISK_LEVEL = "risk_level"
    VOLATILITY = "volatility"
    MAX_DRAWDOWN = "max_drawdown"
    SHARPE_RATIO = "sharpe_ratio"
    VAR = "var"
    
    # Alerts
    ALERT = "alert"
    PRICE_ALERT = "price_alert"
    VOLUME_ALERT = "volume_alert"
    TECHNICAL_ALERT = "technical_alert"
    
    # Time
    TODAY = "today"
    YESTERDAY = "yesterday"
    THIS_WEEK = "this_week"
    THIS_MONTH = "this_month"
    THIS_YEAR = "this_year"
    
    # Common
    LOADING = "loading"
    ERROR = "error"
    SUCCESS = "success"
    WARNING = "warning"
    INFO = "info"
    CONFIRM = "confirm"
    CANCEL = "cancel"
    SAVE = "save"
    DELETE = "delete"
    EDIT = "edit"
    VIEW = "view"
    SEARCH = "search"
    FILTER = "filter"
    SORT = "sort"
    
    # Messages
    NO_DATA_AVAILABLE = "no_data_available"
    OPERATION_SUCCESSFUL = "operation_successful"
    OPERATION_FAILED = "operation_failed"
    INVALID_INPUT = "invalid_input"
    NETWORK_ERROR = "network_error"
    
    # Units
    USD = "usd"
    EUR = "eur"
    GBP = "gbp"
    JPY = "jpy"
    PERCENT = "percent"
    SHARES = "shares"
    DAYS = "days"
    HOURS = "hours"
    MINUTES = "minutes"


@dataclass
class Translation:
    """Translation data for a specific language."""
    language: Language
    translations: Dict[str, str]
    date_format: str
    number_format: Dict[str, str]
    currency_symbol: str
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "language": self.language.value,
            "translations": self.translations,
            "date_format": self.date_format,
            "number_format": self.number_format,
            "currency_symbol": self.currency_symbol
        }
        return result


class I18nManager(LoggerMixin):
    """Internationalization manager."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.translations = {}
        self.default_language = Language.ENGLISH
        self.supported_languages = list(Language)
        
        # Load translations
        self._load_translations()
    
    def _load_translations(self):
        """Load all translation files."""
        try:
            # Define translation data for each language
            translation_data = self._get_translation_data()
            
            for language_code, data in translation_data.items():
                language = Language(language_code)
                
                translation = Translation(
                    language=language,
                    translations=data["translations"],
                    date_format=data["date_format"],
                    number_format=data["number_format"],
                    currency_symbol=data["currency_symbol"]
                )
                
                self.translations[language] = translation
            
            self.logger.info(f"Loaded translations for {len(self.translations)} languages")
            
        except Exception as e:
            self.logger.error(f"Error loading translations: {e}")
            raise
    
    def _get_translation_data(self) -> Dict[str, Dict[str, Any]]:
        """Get translation data for all languages."""
        try:
            return {
                "en": {
                    "translations": {
                        # Navigation
                        "dashboard": "Dashboard",
                        "portfolio": "Portfolio",
                        "trading": "Trading",
                        "analytics": "Analytics",
                        "settings": "Settings",
                        "logout": "Logout",
                        
                        # Trading
                        "buy": "Buy",
                        "sell": "Sell",
                        "hold": "Hold",
                        "market_order": "Market Order",
                        "limit_order": "Limit Order",
                        "stop_loss": "Stop Loss",
                        "take_profit": "Take Profit",
                        
                        # Portfolio
                        "total_value": "Total Value",
                        "total_pnl": "Total P&L",
                        "pnl_percentage": "P&L %",
                        "positions": "Positions",
                        "assets": "Assets",
                        "cash": "Cash",
                        
                        # Risk
                        "risk_level": "Risk Level",
                        "volatility": "Volatility",
                        "max_drawdown": "Max Drawdown",
                        "sharpe_ratio": "Sharpe Ratio",
                        "var": "Value at Risk",
                        
                        # Alerts
                        "alert": "Alert",
                        "price_alert": "Price Alert",
                        "volume_alert": "Volume Alert",
                        "technical_alert": "Technical Alert",
                        
                        # Time
                        "today": "Today",
                        "yesterday": "Yesterday",
                        "this_week": "This Week",
                        "this_month": "This Month",
                        "this_year": "This Year",
                        
                        # Common
                        "loading": "Loading...",
                        "error": "Error",
                        "success": "Success",
                        "warning": "Warning",
                        "info": "Info",
                        "confirm": "Confirm",
                        "cancel": "Cancel",
                        "save": "Save",
                        "delete": "Delete",
                        "edit": "Edit",
                        "view": "View",
                        "search": "Search",
                        "filter": "Filter",
                        "sort": "Sort",
                        
                        # Messages
                        "no_data_available": "No data available",
                        "operation_successful": "Operation successful",
                        "operation_failed": "Operation failed",
                        "invalid_input": "Invalid input",
                        "network_error": "Network error",
                        
                        # Units
                        "usd": "$",
                        "eur": "€",
                        "gbp": "£",
                        "jpy": "¥",
                        "percent": "%",
                        "shares": "shares",
                        "days": "days",
                        "hours": "hours",
                        "minutes": "minutes"
                    },
                    "date_format": "%Y-%m-%d",
                    "number_format": {
                        "decimal_separator": ".",
                        "thousands_separator": ","
                    },
                    "currency_symbol": "$"
                },
                "es": {
                    "translations": {
                        # Navigation
                        "dashboard": "Panel",
                        "portfolio": "Cartera",
                        "trading": "Trading",
                        "analytics": "Análisis",
                        "settings": "Configuración",
                        "logout": "Cerrar sesión",
                        
                        # Trading
                        "buy": "Comprar",
                        "sell": "Vender",
                        "hold": "Mantener",
                        "market_order": "Orden de Mercado",
                        "limit_order": "Orden Límite",
                        "stop_loss": "Stop Loss",
                        "take_profit": "Take Profit",
                        
                        # Portfolio
                        "total_value": "Valor Total",
                        "total_pnl": "P&L Total",
                        "pnl_percentage": "P&L %",
                        "positions": "Posiciones",
                        "assets": "Activos",
                        "cash": "Efectivo",
                        
                        # Risk
                        "risk_level": "Nivel de Riesgo",
                        "volatility": "Volatilidad",
                        "max_drawdown": "Máxima Caída",
                        "sharpe_ratio": "Ratio Sharpe",
                        "var": "Valor en Riesgo",
                        
                        # Alerts
                        "alert": "Alerta",
                        "price_alert": "Alerta de Precio",
                        "volume_alert": "Alerta de Volumen",
                        "technical_alert": "Alerta Técnica",
                        
                        # Time
                        "today": "Hoy",
                        "yesterday": "Ayer",
                        "this_week": "Esta Semana",
                        "this_month": "Este Mes",
                        "this_year": "Este Año",
                        
                        # Common
                        "loading": "Cargando...",
                        "error": "Error",
                        "success": "Éxito",
                        "warning": "Advertencia",
                        "info": "Información",
                        "confirm": "Confirmar",
                        "cancel": "Cancelar",
                        "save": "Guardar",
                        "delete": "Eliminar",
                        "edit": "Editar",
                        "view": "Ver",
                        "search": "Buscar",
                        "filter": "Filtrar",
                        "sort": "Ordenar",
                        
                        # Messages
                        "no_data_available": "No hay datos disponibles",
                        "operation_successful": "Operación exitosa",
                        "operation_failed": "Operación fallida",
                        "invalid_input": "Entrada inválida",
                        "network_error": "Error de red",
                        
                        # Units
                        "usd": "$",
                        "eur": "€",
                        "gbp": "£",
                        "jpy": "¥",
                        "percent": "%",
                        "shares": "acciones",
                        "days": "días",
                        "hours": "horas",
                        "minutes": "minutos"
                    },
                    "date_format": "%d/%m/%Y",
                    "number_format": {
                        "decimal_separator": ",",
                        "thousands_separator": "."
                    },
                    "currency_symbol": "$"
                },
                "fr": {
                    "translations": {
                        # Navigation
                        "dashboard": "Tableau de bord",
                        "portfolio": "Portefeuille",
                        "trading": "Trading",
                        "analytics": "Analytique",
                        "settings": "Paramètres",
                        "logout": "Déconnexion",
                        
                        # Trading
                        "buy": "Acheter",
                        "sell": "Vendre",
                        "hold": "Maintenir",
                        "market_order": "Ordre de marché",
                        "limit_order": "Ordre limite",
                        "stop_loss": "Stop Loss",
                        "take_profit": "Take Profit",
                        
                        # Portfolio
                        "total_value": "Valeur totale",
                        "total_pnl": "P&L total",
                        "pnl_percentage": "P&L %",
                        "positions": "Positions",
                        "assets": "Actifs",
                        "cash": "Espèces",
                        
                        # Risk
                        "risk_level": "Niveau de risque",
                        "volatility": "Volatilité",
                        "max_drawdown": "Drawdown maximum",
                        "sharpe_ratio": "Ratio Sharpe",
                        "var": "Value at Risk",
                        
                        # Alerts
                        "alert": "Alerte",
                        "price_alert": "Alerte de prix",
                        "volume_alert": "Alerte de volume",
                        "technical_alert": "Alerte technique",
                        
                        # Time
                        "today": "Aujourd'hui",
                        "yesterday": "Hier",
                        "this_week": "Cette semaine",
                        "this_month": "Ce mois",
                        "this_year": "Cette année",
                        
                        # Common
                        "loading": "Chargement...",
                        "error": "Erreur",
                        "success": "Succès",
                        "warning": "Avertissement",
                        "info": "Info",
                        "confirm": "Confirmer",
                        "cancel": "Annuler",
                        "save": "Sauvegarder",
                        "delete": "Supprimer",
                        "edit": "Modifier",
                        "view": "Voir",
                        "search": "Rechercher",
                        "filter": "Filtrer",
                        "sort": "Trier",
                        
                        # Messages
                        "no_data_available": "Aucune donnée disponible",
                        "operation_successful": "Opération réussie",
                        "operation_failed": "Opération échouée",
                        "invalid_input": "Entrée invalide",
                        "network_error": "Erreur réseau",
                        
                        # Units
                        "usd": "$",
                        "eur": "€",
                        "gbp": "£",
                        "jpy": "¥",
                        "percent": "%",
                        "shares": "actions",
                        "days": "jours",
                        "hours": "heures",
                        "minutes": "minutes"
                    },
                    "date_format": "%d/%m/%Y",
                    "number_format": {
                        "decimal_separator": ",",
                        "thousands_separator": " "
                    },
                    "currency_symbol": "€"
                },
                "de": {
                    "translations": {
                        # Navigation
                        "dashboard": "Dashboard",
                        "portfolio": "Portfolio",
                        "trading": "Trading",
                        "analytics": "Analytik",
                        "settings": "Einstellungen",
                        "logout": "Abmelden",
                        
                        # Trading
                        "buy": "Kaufen",
                        "sell": "Verkaufen",
                        "hold": "Halten",
                        "market_order": "Marktorder",
                        "limit_order": "Limitorder",
                        "stop_loss": "Stop Loss",
                        "take_profit": "Take Profit",
                        
                        # Portfolio
                        "total_value": "Gesamtwert",
                        "total_pnl": "Gesamt P&L",
                        "pnl_percentage": "P&L %",
                        "positions": "Positionen",
                        "assets": "Vermögenswerte",
                        "cash": "Bargeld",
                        
                        # Risk
                        "risk_level": "Risikostufe",
                        "volatility": "Volatilität",
                        "max_drawdown": "Maximaler Drawdown",
                        "sharpe_ratio": "Sharpe Ratio",
                        "var": "Value at Risk",
                        
                        # Alerts
                        "alert": "Alarm",
                        "price_alert": "Preisalarm",
                        "volume_alert": "Volumenalarm",
                        "technical_alert": "Technische Alarm",
                        
                        # Time
                        "today": "Heute",
                        "yesterday": "Gestern",
                        "this_week": "Diese Woche",
                        "this_month": "Dieser Monat",
                        "this_year": "Dieses Jahr",
                        
                        # Common
                        "loading": "Laden...",
                        "error": "Fehler",
                        "success": "Erfolg",
                        "warning": "Warnung",
                        "info": "Info",
                        "confirm": "Bestätigen",
                        "cancel": "Abbrechen",
                        "save": "Speichern",
                        "delete": "Löschen",
                        "edit": "Bearbeiten",
                        "view": "Anzeigen",
                        "search": "Suchen",
                        "filter": "Filtern",
                        "sort": "Sortieren",
                        
                        # Messages
                        "no_data_available": "Keine Daten verfügbar",
                        "operation_successful": "Operation erfolgreich",
                        "operation_failed": "Operation fehlgeschlagen",
                        "invalid_input": "Ungültige Eingabe",
                        "network_error": "Netzwerkfehler",
                        
                        # Units
                        "usd": "$",
                        "eur": "€",
                        "gbp": "£",
                        "jpy": "¥",
                        "percent": "%",
                        "shares": "Aktien",
                        "days": "Tage",
                        "hours": "Stunden",
                        "minutes": "Minuten"
                    },
                    "date_format": "%d.%m.%Y",
                    "number_format": {
                        "decimal_separator": ",",
                        "thousands_separator": "."
                    },
                    "currency_symbol": "€"
                },
                "ja": {
                    "translations": {
                        # Navigation
                        "dashboard": "ダッシュボード",
                        "portfolio": "ポートフォリオ",
                        "trading": "トレーディング",
                        "analytics": "分析",
                        "settings": "設定",
                        "logout": "ログアウト",
                        
                        # Trading
                        "buy": "買い",
                        "sell": "売り",
                        "hold": "保持",
                        "market_order": "市場注文",
                        "limit_order": "指値注文",
                        "stop_loss": "ストップロス",
                        "take_profit": "テイクプロフィット",
                        
                        # Portfolio
                        "total_value": "総価値",
                        "total_pnl": "総損益",
                        "pnl_percentage": "損益 %",
                        "positions": "ポジション",
                        "assets": "資産",
                        "cash": "現金",
                        
                        # Risk
                        "risk_level": "リスクレベル",
                        "volatility": "ボラティリティ",
                        "max_drawdown": "最大ドローダウン",
                        "sharpe_ratio": "シャープレシオ",
                        "var": "バリュー・アット・リスク",
                        
                        # Alerts
                        "alert": "アラート",
                        "price_alert": "価格アラート",
                        "volume_alert": "出来高アラート",
                        "technical_alert": "テクニカルアラート",
                        
                        # Time
                        "today": "今日",
                        "yesterday": "昨日",
                        "this_week": "今週",
                        "this_month": "今月",
                        "this_year": "今年",
                        
                        # Common
                        "loading": "読み込み中...",
                        "error": "エラー",
                        "success": "成功",
                        "warning": "警告",
                        "info": "情報",
                        "confirm": "確認",
                        "cancel": "キャンセル",
                        "save": "保存",
                        "delete": "削除",
                        "edit": "編集",
                        "view": "表示",
                        "search": "検索",
                        "filter": "フィルター",
                        "sort": "ソート",
                        
                        # Messages
                        "no_data_available": "データがありません",
                        "operation_successful": "操作が成功しました",
                        "operation_failed": "操作が失敗しました",
                        "invalid_input": "入力が無効です",
                        "network_error": "ネットワークエラー",
                        
                        # Units
                        "usd": "$",
                        "eur": "€",
                        "gbp": "£",
                        "jpy": "¥",
                        "percent": "%",
                        "shares": "株",
                        "days": "日",
                        "hours": "時間",
                        "minutes": "分"
                    },
                    "date_format": "%Y年%m月%d日",
                    "number_format": {
                        "decimal_separator": ".",
                        "thousands_separator": ","
                    },
                    "currency_symbol": "¥"
                },
                "zh": {
                    "translations": {
                        # Navigation
                        "dashboard": "仪表板",
                        "portfolio": "投资组合",
                        "trading": "交易",
                        "analytics": "分析",
                        "settings": "设置",
                        "logout": "退出",
                        
                        # Trading
                        "buy": "买入",
                        "sell": "卖出",
                        "hold": "持有",
                        "market_order": "市价单",
                        "limit_order": "限价单",
                        "stop_loss": "止损",
                        "take_profit": "止盈",
                        
                        # Portfolio
                        "total_value": "总价值",
                        "total_pnl": "总损益",
                        "pnl_percentage": "损益 %",
                        "positions": "持仓",
                        "assets": "资产",
                        "cash": "现金",
                        
                        # Risk
                        "risk_level": "风险等级",
                        "volatility": "波动性",
                        "max_drawdown": "最大回撤",
                        "sharpe_ratio": "夏普比率",
                        "var": "风险价值",
                        
                        # Alerts
                        "alert": "警报",
                        "price_alert": "价格警报",
                        "volume_alert": "成交量警报",
                        "technical_alert": "技术警报",
                        
                        # Time
                        "today": "今天",
                        "yesterday": "昨天",
                        "this_week": "本周",
                        "this_month": "本月",
                        "this_year": "今年",
                        
                        # Common
                        "loading": "加载中...",
                        "error": "错误",
                        "success": "成功",
                        "warning": "警告",
                        "info": "信息",
                        "confirm": "确认",
                        "cancel": "取消",
                        "save": "保存",
                        "delete": "删除",
                        "edit": "编辑",
                        "view": "查看",
                        "search": "搜索",
                        "filter": "筛选",
                        "sort": "排序",
                        
                        # Messages
                        "no_data_available": "无可用数据",
                        "operation_successful": "操作成功",
                        "operation_failed": "操作失败",
                        "invalid_input": "输入无效",
                        "network_error": "网络错误",
                        
                        # Units
                        "usd": "$",
                        "eur": "€",
                        "gbp": "£",
                        "jpy": "¥",
                        "percent": "%",
                        "shares": "股",
                        "days": "天",
                        "hours": "小时",
                        "minutes": "分钟"
                    },
                    "date_format": "%Y年%m月%d日",
                    "number_format": {
                        "decimal_separator": ".",
                        "thousands_separator": ","
                    },
                    "currency_symbol": "¥"
                },
                "pt": {
                    "translations": {
                        # Navigation
                        "dashboard": "Painel",
                        "portfolio": "Carteira",
                        "trading": "Trading",
                        "analytics": "Análise",
                        "settings": "Configurações",
                        "logout": "Sair",
                        
                        # Trading
                        "buy": "Comprar",
                        "sell": "Vender",
                        "hold": "Manter",
                        "market_order": "Ordem de Mercado",
                        "limit_order": "Ordem Limite",
                        "stop_loss": "Stop Loss",
                        "take_profit": "Take Profit",
                        
                        # Portfolio
                        "total_value": "Valor Total",
                        "total_pnl": "P&L Total",
                        "pnl_percentage": "P&L %",
                        "positions": "Posições",
                        "assets": "Ativos",
                        "cash": "Dinheiro",
                        
                        # Risk
                        "risk_level": "Nível de Risco",
                        "volatility": "Volatilidade",
                        "max_drawdown": "Drawdown Máximo",
                        "sharpe_ratio": "Ratio Sharpe",
                        "var": "Valor em Risco",
                        
                        # Alerts
                        "alert": "Alerta",
                        "price_alert": "Alerta de Preço",
                        "volume_alert": "Alerta de Volume",
                        "technical_alert": "Alerta Técnica",
                        
                        # Time
                        "today": "Hoje",
                        "yesterday": "Ontem",
                        "this_week": "Esta Semana",
                        "this_month": "Este Mês",
                        "this_year": "Este Ano",
                        
                        # Common
                        "loading": "Carregando...",
                        "error": "Erro",
                        "success": "Sucesso",
                        "warning": "Aviso",
                        "info": "Informação",
                        "confirm": "Confirmar",
                        "cancel": "Cancelar",
                        "save": "Salvar",
                        "delete": "Excluir",
                        "edit": "Editar",
                        "view": "Ver",
                        "search": "Buscar",
                        "filter": "Filtrar",
                        "sort": "Ordenar",
                        
                        # Messages
                        "no_data_available": "Nenhum dado disponível",
                        "operation_successful": "Operação bem-sucedida",
                        "operation_failed": "Operação falhou",
                        "invalid_input": "Entrada inválida",
                        "network_error": "Erro de rede",
                        
                        # Units
                        "usd": "$",
                        "eur": "€",
                        "gbp": "£",
                        "jpy": "¥",
                        "percent": "%",
                        "shares": "ações",
                        "days": "dias",
                        "hours": "horas",
                        "minutes": "minutos"
                    },
                    "date_format": "%d/%m/%Y",
                    "number_format": {
                        "decimal_separator": ",",
                        "thousands_separator": "."
                    },
                    "currency_symbol": "R$"
                },
                "ru": {
                    "translations": {
                        # Navigation
                        "dashboard": "Панель",
                        "portfolio": "Портфель",
                        "trading": "Торговля",
                        "analytics": "Аналитика",
                        "settings": "Настройки",
                        "logout": "Выйти",
                        
                        # Trading
                        "buy": "Купить",
                        "sell": "Продать",
                        "hold": "Держать",
                        "market_order": "Рыночный ордер",
                        "limit_order": "Лимитный ордер",
                        "stop_loss": "Стоп-лосс",
                        "take_profit": "Тейк-профит",
                        
                        # Portfolio
                        "total_value": "Общая стоимость",
                        "total_pnl": "Общий P&L",
                        "pnl_percentage": "P&L %",
                        "positions": "Позиции",
                        "assets": "Активы",
                        "cash": "Наличные",
                        
                        # Risk
                        "risk_level": "Уровень риска",
                        "volatility": "Волатильность",
                        "max_drawdown": "Максимальная просадка",
                        "sharpe_ratio": "Коэффициент Шарпа",
                        "var": "Стоимость под риском",
                        
                        # Alerts
                        "alert": "Оповещение",
                        "price_alert": "Ценовое оповещение",
                        "volume_alert": "Объемное оповещение",
                        "technical_alert": "Техническое оповещение",
                        
                        # Time
                        "today": "Сегодня",
                        "yesterday": "Вчера",
                        "this_week": "Эта неделя",
                        "this_month": "Этот месяц",
                        "this_year": "Этот год",
                        
                        # Common
                        "loading": "Загрузка...",
                        "error": "Ошибка",
                        "success": "Успех",
                        "warning": "Предупреждение",
                        "info": "Информация",
                        "confirm": "Подтвердить",
                        "cancel": "Отмена",
                        "save": "Сохранить",
                        "delete": "Удалить",
                        "edit": "Редактировать",
                        "view": "Просмотр",
                        "search": "Поиск",
                        "filter": "Фильтр",
                        "sort": "Сортировка",
                        
                        # Messages
                        "no_data_available": "Нет доступных данных",
                        "operation_successful": "Операция выполнена успешно",
                        "operation_failed": "Операция не удалась",
                        "invalid_input": "Недопустимый ввод",
                        "network_error": "Ошибка сети",
                        
                        # Units
                        "usd": "$",
                        "eur": "€",
                        "gbp": "£",
                        "jpy": "¥",
                        "percent": "%",
                        "shares": "акции",
                        "days": "дней",
                        "hours": "часов",
                        "minutes": "минут"
                    },
                    "date_format": "%d.%m.%Y",
                    "number_format": {
                        "decimal_separator": ",",
                        "thousands_separator": " "
                    },
                    "currency_symbol": "₽"
                },
                "it": {
                    "translations": {
                        # Navigation
                        "dashboard": "Pannello",
                        "portfolio": "Portafoglio",
                        "trading": "Trading",
                        "analytics": "Analitica",
                        "settings": "Impostazioni",
                        "logout": "Esci",
                        
                        # Trading
                        "buy": "Compra",
                        "sell": "Vendi",
                        "hold": "Mantieni",
                        "market_order": "Ordine di Mercato",
                        "limit_order": "Ordine Limite",
                        "stop_loss": "Stop Loss",
                        "take_profit": "Take Profit",
                        
                        # Portfolio
                        "total_value": "Valore Totale",
                        "total_pnl": "P&L Totale",
                        "pnl_percentage": "P&L %",
                        "positions": "Posizioni",
                        "assets": "Attività",
                        "cash": "Contante",
                        
                        # Risk
                        "risk_level": "Livello di Rischio",
                        "volatility": "Volatilità",
                        "max_drawdown": "Drawdown Massimo",
                        "sharpe_ratio": "Ratio Sharpe",
                        "var": "Value at Risk",
                        
                        # Alerts
                        "alert": "Allarme",
                        "price_alert": "Allarme Prezzo",
                        "volume_alert": "Allarme Volume",
                        "technical_alert": "Allarme Tecnica",
                        
                        # Time
                        "today": "Oggi",
                        "yesterday": "Ieri",
                        "this_week": "Questa settimana",
                        "this_month": "Questo mese",
                        "this_year": "Questo anno",
                        
                        # Common
                        "loading": "Caricamento...",
                        "error": "Errore",
                        "success": "Successo",
                        "warning": "Avviso",
                        "info": "Informazioni",
                        "confirm": "Conferma",
                        "cancel": "Annulla",
                        "save": "Salva",
                        "delete": "Elimina",
                        "edit": "Modifica",
                        "view": "Visualizza",
                        "search": "Cerca",
                        "filter": "Filtra",
                        "sort": "Ordina",
                        
                        # Messages
                        "no_data_available": "Nessun dato disponibile",
                        "operation_successful": "Operazione riuscita",
                        "operation_failed": "Operazione fallita",
                        "invalid_input": "Input non valido",
                        "network_error": "Errore di rete",
                        
                        # Units
                        "usd": "$",
                        "eur": "€",
                        "gbp": "£",
                        "jpy": "¥",
                        "percent": "%",
                        "shares": "azioni",
                        "days": "giorni",
                        "hours": "ore",
                        "minutes": "minuti"
                    },
                    "date_format": "%d/%m/%Y",
                    "number_format": {
                        "decimal_separator": ",",
                        "thousands_separator": "."
                    },
                    "currency_symbol": "€"
                },
                "ar": {
                    "translations": {
                        # Navigation
                        "dashboard": "لوحة القيادة",
                        "portfolio": "محففظة",
                        "trading": "تداول",
                        "analytics": "تحليل",
                        "settings": "الإعدادات",
                        "logout": "تسجيل الخروج",
                        
                        # Trading
                        "buy": "شراء",
                        "sell": "بيع",
                        "hold": "احتفاظ",
                        "market_order": "أمر السوق",
                        "limit_order": "أمر محدد",
                        "stop_loss": "وقف الخسارة",
                        "take_profit": "أخذ الربح",
                        
                        # Portfolio
                        "total_value": "القيمة الإجمالية",
                        "total_pnl": "إجمالي الربح والخسارة",
                        "pnl_percentage": "الربح والخسارة %",
                        "positions": "المراكز",
                        "assets": "الأصول",
                        "cash": "نقد",
                        
                        # Risk
                        "risk_level": "مستوى المخاطرة",
                        "volatility": "التقلب",
                        "max_drawdown": "الحد الأقصى للخسارة",
                        "sharpe_ratio": "نسبة شارب",
                        "var": "القيمة المعرضة للخطر",
                        
                        # Alerts
                        "alert": "تنبيه",
                        "price_alert": "تنبيه السعر",
                        "volume_alert": "تنبيه الحجم",
                        "technical_alert": "تنبيه تقني",
                        
                        # Time
                        "today": "اليوم",
                        "yesterday": "أمس",
                        "this_week": "هذا الأسبوع",
                        "this_month": "هذا الشهر",
                        "this_year": "هذا العام",
                        
                        # Common
                        "loading": "جاري التحميل...",
                        "error": "خطأ",
                        "success": "نجاح",
                        "warning": "تحذير",
                        "info": "معلومات",
                        "confirm": "تأكيد",
                        "cancel": "إلغاء",
                        "save": "حفظ",
                        "delete": "حذف",
                        "edit": "تعديل",
                        "view": "عرض",
                        "search": "بحث",
                        "filter": "تصفية",
                        "sort": "ترتيب",
                        
                        # Messages
                        "no_data_available": "لا توجد بيانات متاحة",
                        "operation_successful": "عملية ناجحة",
                        "operation_failed": "فشلت العملية",
                        "invalid_input": "إدخال غير صالح",
                        "network_error": "خطأ في الشبكة",
                        
                        # Units
                        "usd": "$",
                        "eur": "€",
                        "gbp": "£",
                        "jpy": "¥",
                        "percent": "%",
                        "shares": "أسهم",
                        "days": "أيام",
                        "hours": "ساعات",
                        "minutes": "دقائق"
                    },
                    "date_format": "%Y/%m/%d",
                    "number_format": {
                        "decimal_separator": ".",
                        "thousands_separator": ","
                    },
                    "currency_symbol": "$"
                }
            }
            
            return translation_data
        
        except Exception as e:
            self.logger.error(f"Error getting translation data: {e}")
            return {}
    
    def translate(self, key: str, language: Language = None, **kwargs) -> str:
        """Translate a key to the specified language."""
        try:
            if language is None:
                language = self.default_language
            
            if language not in self.translations:
                language = self.default_language
            
            translation = self.translations[language]
            
            # Get the translation
            translated_text = translation.translations.get(key, key)
            
            # Apply formatting if kwargs provided
            if kwargs:
                try:
                    translated_text = translated_text.format(**kwargs)
                except (KeyError, ValueError) as e:
                    self.logger.warning(f"Error formatting translation: {e}")
                    translated_text = key
            
            return translated_text
        
        except Exception as e:
            self.logger.error(f"Error translating key '{key}': {e}")
            return key
    
    def format_date(self, date: datetime, language: Language = None) -> str:
        """Format date according to language preferences."""
        try:
            if language is None:
                language = self.default_language
            
            if language not in self.translations:
                language = self.default_language
            
            translation = self.translations[language]
            
            return date.strftime(translation.date_format)
        
        except Exception as e:
            self.logger.error(f"Error formatting date: {e}")
            return date.strftime("%Y-%m-%d")
    
    def format_number(self, number: Union[int, float], language: Language = None) -> str:
        """Format number according to language preferences."""
        try:
            if language is None:
                language = self.default_language
            
            if language not in self.translations:
                language = self.default_language
            
            translation = self.translations[language]
            number_format = translation.number_format
            
            # Format with appropriate separators
            if isinstance(number, float):
                formatted = f"{number:,.2f}".replace(",", "TEMP").replace(".", number_format["decimal_separator"]).replace("TEMP", number_format["thousands_separator"])
            else:
                formatted = f"{number:,}".replace(",", number_format["thousands_separator"])
            
            return formatted
        
        except Exception as e:
            self.logger.error(f"Error formatting number: {e}")
            return str(number)
    
    def format_currency(self, amount: Union[int, float], language: Language = None) -> str:
        """Format currency according to language preferences."""
        try:
            if language is None:
                language = self.default_language
            
            if language not in self.translations:
                language = self.default_language
            
            translation = self.translations[language]
            
            # Format the amount
            formatted_amount = self.format_number(amount, language)
            
            # Add currency symbol
            if language in [Language.ARABIC]:
                return f"{formatted_amount} {translation.currency_symbol}"
            else:
                return f"{translation.currency_symbol}{formatted_amount}"
        
        except Exception as e:
            self.logger.error(f"Error formatting currency: {e}")
            return f"${amount:,.2f}"
    
    def get_language_direction(self, language: Language = None) -> str:
        """Get text direction for the language (RTL/LTR)."""
        try:
            if language is None:
                language = self.default_language
            
            # Arabic is RTL
            if language == Language.ARABIC:
                return "rtl"
            else:
                return "ltr"
        
        except Exception as e:
            self.logger.error(f"Error getting language direction: {e}")
            return "ltr"
    
    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get list of supported languages."""
        try:
            languages = []
            
            for language in self.supported_languages:
                # Get native language name
                native_name = self.translate("language_name", language)
                
                languages.append({
                    "code": language.value,
                    "name": language.value.upper(),
                    "native_name": native_name if native_name != "language_name" else language.value.upper()
                })
            
            return languages
        
        except Exception as e:
            self.logger.error(f"Error getting supported languages: {e}")
            return []
    
    def detect_language_from_request(self, request_headers: Dict[str, str]) -> Language:
        """Detect language from HTTP request headers."""
        try:
            # Check Accept-Language header
            accept_language = request_headers.get("Accept-Language", "")
            
            if accept_language:
                # Parse Accept-Language header
                preferred_languages = [lang.split(";")[0].strip() for lang in accept_language.split(",")]
                
                for lang_code in preferred_languages:
                    # Handle language codes like "en-US"
                    primary_code = lang_code.split("-")[0]
                    
                    for language in self.supported_languages:
                        if language.value == primary_code or language.value == lang_code:
                            return language
            
            # Default to English
            return self.default_language
        
        except Exception as e:
            self.logger.error(f"Error detecting language: {e}")
            return self.default_language
    
    def get_translations_for_frontend(self, language: Language = None) -> Dict[str, Any]:
        """Get all translations for frontend use."""
        try:
            if language is None:
                language = self.default_language
            
            if language not in self.translations:
                language = self.default_language
            
            translation = self.translations[language]
            
            return {
                "language": language.value,
                "translations": translation.translations,
                "date_format": translation.date_format,
                "number_format": translation.number_format,
                "currency_symbol": translation.currency_symbol,
                "direction": self.get_language_direction(language),
                "supported_languages": self.get_supported_languages()
            }
        
        except Exception as e:
            self.logger.error(f"Error getting translations for frontend: {e}")
            return {}


# Global instance
i18n_manager = I18nManager()


def get_i18n_manager() -> I18nManager:
    """Get i18n manager instance."""
    return i18n_manager


# Utility functions
def t(key: str, language: str = None, **kwargs) -> str:
    """Translation function for templates and views."""
    lang = Language(language) if language else None
    return i18n_manager.translate(key, lang, **kwargs)


def format_date(date: datetime, language: str = None) -> str:
    """Format date with language support."""
    lang = Language(language) if language else None
    return i18n_manager.format_date(date, lang)


def format_currency(amount: Union[int, float], language: str = None) -> str:
    """Format currency with language support."""
    lang = Language(language) if language else None
    return i18n_manager.format_currency(amount, lang)


def format_number(number: Union[int, float], language: str = None) -> str:
    """Format number with language support."""
    lang = Language(language) if language else None
    return i18n_manager.format_number(number, lang)
