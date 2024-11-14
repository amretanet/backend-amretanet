## Backend Social Media Audit
**About**
- Backend Social Media Audit merupakan sistem yang menyediakan layanan API untuk kebutuhan audit akun sosial media.

**Subdomain**
- 

**Related Link**
- [FastAPI](https://fastapi.tiangolo.com/)
- [MongoDB](https://www.mongodb.com/)

**Folder Structure**
- List Route: `/app/routes/v1`
- Menambahkan Modules atau function: `/app/modules`
- Menambahkan Model atau CRUD data: `/app/models/BaseModel.py`
- Tempat mendaftarkan endpoint atau routes: `/app/routes/v1/main.py`
- Database Connection: `/app/modules/database.py`
- Projection (field field untuk JSON response) `/app/modules/projections.py`
- Tipe data untuk Parameter `/app/modules/data_model.py`
- Logging betterstack dan telegram `/app/modules/logger.py`
- RSA encriptions `/app/modules/cryptography.py`
- Function usable `/app/modules/generals.py`

**Notes**
- setiap endpoint akan mengecek verifikasi pada endpoint auth untuk pengecekan token
- untuk password menggunakan encription RSA dengan mencocokan public key dari FE dengan private key dari BE


**Requirements**
- Python versi 3 keatas
- install python3-venv (khusus OS linux)

**Run Project**
1.  clone repository: https://gitlab.kabayanconsulting.co.id/pt-kabayan-aishwarya-nusantara/social-media-audit/backend-socmed-audit.git
2.  copy .env.example menjadi .env
3.  buatkan venv
	`python3 -m venv venv`
4.  aktifkan venv
	`source venv/bin/activate`
5.  install package
	`pip install -r requirements.txt`
6. 	run service
	`uvicorn app.main:app --reload --port=<port>`

**Deployment**
1.  clone repository: https://gitlab.kabayanconsulting.co.id/pt-kabayan-aishwarya-nusantara/social-media-audit/backend-socmed-audit.git
2.  copy .env.example menjadi .env
3.  buatkan venv
	`python3 -m venv venv`
4.  aktifkan venv
	`source venv/bin/activate`
5.  install package
	`pip install -r requirements.txt`
6.  jalankan service backend nya dengan perintah
	`docker compose up -d`
7. 	deploy ulang
	`git pull origin <branch> && docker compose up -d --build`
