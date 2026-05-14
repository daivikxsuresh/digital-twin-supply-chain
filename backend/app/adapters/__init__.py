from app.adapters.base import BaseERPAdapter, BaseTMSAdapter
from app.adapters.erp.csv_erp import CSVERPAdapter
from app.adapters.tms.csv_tms import CSVTMSAdapter

# Registry maps source_system name → adapter class.
# Add new integrations here — nothing else in the codebase needs to change.
ADAPTER_REGISTRY: dict[str, type[BaseERPAdapter] | type[BaseTMSAdapter]] = {
    "CSV_ERP": CSVERPAdapter,
    "CSV_TMS": CSVTMSAdapter,
    # "SAP_ERP": SAPERPAdapter,       # uncomment when implemented
    # "NETSUITE_ERP": NetSuiteAdapter, # uncomment when implemented
}

__all__ = [
    "BaseERPAdapter",
    "BaseTMSAdapter",
    "ADAPTER_REGISTRY",
]
