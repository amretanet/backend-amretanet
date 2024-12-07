from io import BytesIO
from fpdf import FPDF
from PIL import Image
import os
from dotenv import load_dotenv
from urllib.parse import urljoin

load_dotenv()

PROJECT_PATH = os.getenv("PROJECT_PATH")


def ConvertImage(input_path: str, output_path: str):
    with Image.open(input_path) as img:
        img.save(output_path, format="PNG", interlace=False)


def CreateInvoiceHeader(pdf: FPDF):
    logo_path = urljoin(PROJECT_PATH, "assets/images/utils/short-logo.png")
    # convert logo
    try:
        temp_logo_path = "/tmp/converted_image.png"
        ConvertImage(logo_path, temp_logo_path)
        logo_path = temp_logo_path
    except Exception as e:
        raise RuntimeError(f"Error converting PNG: {e}")

    # add header
    pdf.image(logo_path, x=95, y=10, w=20, h=0)
    pdf.set_y(33)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "AMRETA NETWORK", border=False, ln=True, align="C")
    pdf.set_y(38)
    pdf.cell(0, 10, "Solusi Internet Unlimited", border=False, ln=True, align="C")
    pdf.set_y(43)
    pdf.set_font("Arial", "", 10)
    pdf.cell(
        0,
        10,
        "whatsapp: 08999094340 | email: sandi@amreta.net",
        border=False,
        ln=True,
        align="C",
    )
    pdf.set_y(47)
    pdf.cell(
        0,
        10,
        "Cipacing, Jatinangor",
        border=False,
        ln=True,
        align="C",
    )
    pdf.set_y(58)
    pdf.line(10, 58, 200, 58)


def CreateInvoiceBody(pdf: FPDF):
    # invoice title
    pdf.set_font("Arial", "B", 14)
    pdf.set_y(60)
    pdf.cell(0, 10, "INVOICE", border=False, ln=True, align="R")
    pdf.set_font("Arial", "B", 12)
    pdf.set_y(65)
    pdf.cell(0, 10, "Periode 10 Desember 2024", border=False, ln=True, align="R")
    pdf.set_y(70)
    pdf.cell(
        0,
        10,
        "BELUM DIBAYAR",
        border=False,
        ln=True,
        align="R",
    )

    # customer welcome
    pdf.set_font("Arial", "", 12)
    pdf.cell(
        0, 10, "Kepada Yth. Pelanggan Amreta Network", border=False, ln=False, align="L"
    )
    pdf.ln(10)
    # service number
    pdf.set_font("Arial", "", 12)
    pdf.cell(55, 10, "Nomor Layanan", border=False, ln=False, align="L")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(2, 10, ":", border=False, ln=False, align="L")
    pdf.cell(0, 10, "999", border=False, ln=True, align="L")
    # name
    pdf.set_font("Arial", "", 12)
    pdf.cell(55, 10, "Nama Pelanggan", border=False, ln=False, align="L")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(2, 10, ":", border=False, ln=False, align="L")
    pdf.cell(0, 10, "Hanhan Septian", border=False, ln=True, align="L")
    # address
    pdf.set_font("Arial", "", 12)
    pdf.cell(55, 10, "Alamat", border=False, ln=False, align="L")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(2, 10, ":", border=False, ln=False, align="L")
    pdf.multi_cell(
        0,
        10,
        "Jln. Ketut Sari, Cibabat, Cimahi - Jawa Barat",
        border=False,
        align="L",
    )
    # phone number
    pdf.set_font("Arial", "", 12)
    pdf.cell(55, 10, "Nomor Telepon", border=False, ln=False, align="L")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(2, 10, ":", border=False, ln=False, align="L")
    pdf.cell(0, 10, "081218030424", border=False, ln=True, align="L")
    # invoice date
    pdf.set_font("Arial", "", 12)
    pdf.cell(55, 10, "Tanggal Invoice", border=False, ln=False, align="L")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(2, 10, ":", border=False, ln=False, align="L")
    pdf.cell(0, 10, "04 Desember 2024", border=False, ln=True, align="L")
    # due date
    pdf.set_font("Arial", "", 12)
    pdf.cell(55, 10, "Jatuh Tempo", border=False, ln=False, align="L")
    pdf.set_font("Arial", "B", 12)
    pdf.cell(2, 10, ":", border=False, ln=False, align="L")
    pdf.cell(0, 10, "04 Desember 2024", border=False, ln=True, align="L")
    # package
    pdf.ln(7)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(20, 10, "No", border=False, ln=False, align="L")
    pdf.cell(150, 10, "Paket", border=False, ln=False, align="L")
    pdf.cell(0, 10, "Harga", border=False, ln=True, align="R")
    for item in range(1):
        print(item)
        pdf.set_font("Arial", "", 12)
        pdf.cell(20, 10, str(item + 1), border=False, ln=False, align="L")
        pdf.cell(150, 10, "Amreta 20MB", border=False, ln=False, align="L")
        pdf.cell(0, 10, "Rp200000", border=False, ln=True, align="R")

    # amount
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Sub Total: Rp500000", border=False, ln=False, align="R")
    pdf.ln(7)
    pdf.cell(0, 10, "Kode Unik: 525", border=False, ln=False, align="R")
    pdf.ln(7)
    pdf.cell(0, 10, "Total Tagihan: Rp525000", border=False, ln=False, align="R")
    pdf.ln(10)
    # notes
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(255, 28, 40)
    pdf.cell(0, 10, "CATATAN:", border=False, ln=False, align="L")
    pdf.ln(7)
    pdf.set_font("Arial", "I", 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(
        0,
        10,
        "*Mohon melakukan pembayaran dengan nominal tepat Rp525000 sesuai Total Tagihan*",
        border=False,
        ln=False,
        align="L",
    )
    pdf.ln(15)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(
        0,
        10,
        "Pembayaran Bisa Dilakukan Menggunakan Metode Transfer",
        border=False,
        ln=False,
        align="L",
    )
    pdf.ln(7)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(
        0,
        10,
        "Konfirmasi Pembayaran Anda Melalui Kontak Kami:",
        border=False,
        ln=False,
        align="L",
    )
    # admin contact
    pdf.ln(7)
    pdf.set_font("Arial", "", 12)
    pdf.cell(30, 10, "Email", border=False, ln=False, align="L")
    pdf.cell(2, 10, ":", border=False, ln=False, align="L")
    pdf.cell(2, 10, "sandi@amreta.net", border=False, ln=False, align="L")
    pdf.ln(7)
    pdf.set_font("Arial", "", 12)
    pdf.cell(30, 10, "Whatsapp", border=False, ln=False, align="L")
    pdf.cell(2, 10, ":", border=False, ln=False, align="L")
    pdf.cell(2, 10, "08999094340", border=False, ln=False, align="L")
    # footer
    pdf.set_y(-30)
    pdf.set_font("Arial", "BI", 12)
    pdf.cell(
        0,
        10,
        "Terimakasih Telah Melakukan Pembayaran Tepat Waktu ^_^",
        border=False,
        ln=False,
        align="C",
    )


def CreateInvoicePDF() -> BytesIO:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # create header
    CreateInvoiceHeader(pdf)

    # create body
    CreateInvoiceBody(pdf)

    # save to pdf
    pdf_bytes = BytesIO()
    pdf_output = pdf.output(dest="S").encode("latin1")
    pdf_bytes.write(pdf_output)
    pdf_bytes.seek(0)
    return pdf_bytes
