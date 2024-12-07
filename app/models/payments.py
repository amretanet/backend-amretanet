from pydantic import BaseModel


# schemas
class PaymentInsertData(BaseModel):
    id_invoice: str
    method: str
