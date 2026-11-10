import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client

# =========================================================
# SIA BUDIDAYA LELE
# =========================================================
st.set_page_config(page_title="SIA Budidaya Lele", page_icon="🐟", layout="wide")

KAS, PIUTANG, UTANG, MODAL, JUAL = "1110", "1120", "2110", "3110", "4110"
AKUN_BELI = {"Pakan": "1210", "Bibit": "1220", "Operasional": "5130"}
AKUN_PAKAI = {"Pakan": ("5110", "1210"), "Bibit": ("5120", "1220")}
PAGES = ["Dashboard", "Pembelian", "Penjualan", "Peralatan", "Akses Cepat"]
AKSES = ["Jurnal Umum", "Buku Besar", "Buku Pembantu", "Neraca", "Laba Rugi"]

AKUN_DEFAULT = [
    {"kode": "1110", "nama": "Kas", "tipe": "Aset"},
    {"kode": "1120", "nama": "Piutang Usaha", "tipe": "Aset"},
    {"kode": "1210", "nama": "Persediaan Pakan", "tipe": "Aset"},
    {"kode": "1220", "nama": "Persediaan Bibit Lele", "tipe": "Aset"},
    {"kode": "1310", "nama": "Peralatan", "tipe": "Aset"},
    {"kode": "1311", "nama": "Akumulasi Penyusutan Peralatan", "tipe": "Aset"},
    {"kode": "2110", "nama": "Utang Usaha", "tipe": "Kewajiban"},
    {"kode": "3110", "nama": "Modal Pemilik", "tipe": "Ekuitas"},
    {"kode": "4110", "nama": "Penjualan Lele", "tipe": "Pendapatan"},
    {"kode": "5110", "nama": "Beban Pakan", "tipe": "Beban"},
    {"kode": "5120", "nama": "Beban Bibit", "tipe": "Beban"},
    {"kode": "5130", "nama": "Beban Operasional", "tipe": "Beban"},
    {"kode": "5140", "nama": "Beban Penyusutan", "tipe": "Beban"},
]

KOLOM_KOSONG = {
    "accounts": ["kode", "nama", "tipe"],
    "journals": ["id", "tanggal", "keterangan", "ref_type"],
    "journal_lines": ["id", "journal_id", "kode_akun", "debit", "kredit"],
    "purchases": ["id", "tanggal", "supplier", "kategori", "item", "qty", "satuan",
                  "harga", "total", "metode", "jatuh_tempo", "lunas"],
    "sales": ["id", "tanggal", "pembeli", "kg", "harga_kg", "total", "metode", "lunas"],
    "stock_moves": ["id", "tanggal", "kategori", "item", "qty"],
    "equipment": ["id", "nama", "tanggal", "harga", "umur_bulan", "residu"],
}


# ------------------------- Koneksi & database -------------------------
@st.cache_resource
def db():
    """Membaca kredensial dari Streamlit secrets atau kunci.toml."""
    url = key = None
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
    except Exception:
        pass

    if not url or not key:
        try:
            import tomllib
            with open("kunci.toml", "rb") as f:
                cfg = tomllib.load(f)
            url = cfg.get("SUPABASE_URL")
            key = cfg.get("SUPABASE_KEY")
        except FileNotFoundError:
            raise RuntimeError(
                "File konfigurasi tidak ditemukan. Buat kunci.toml di folder yang sama "
                "dengan app.py, berisi SUPABASE_URL dan SUPABASE_KEY."
            )
        except Exception as e:
            raise RuntimeError(f"Gagal membaca kunci.toml: {e}")

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL atau SUPABASE_KEY belum diisi. Periksa kunci.toml "
            "atau .streamlit/secrets.toml."
        )
    return create_client(str(url).split("/rest/v1")[0].rstrip("/"), str(key))


def ambil_semua(query_fn, batas=1000):
    """Mengambil seluruh baris dengan pagination."""
    hasil, mulai = [], 0
    while True:
        data = query_fn().range(mulai, mulai + batas - 1).execute().data or []
        hasil.extend(data)
        if len(data) < batas:
            return hasil
        mulai += batas


def tbl(nama):
    if nama not in KOLOM_KOSONG:
        raise ValueError(f"Nama tabel tidak dikenal: {nama}")
    urut = "kode" if nama == "accounts" else "id"
    data = ambil_semua(lambda: db().table(nama).select("*").order(urut))
    # DataFrame kosong tetap memiliki kolom yang benar agar tidak memicu KeyError.
    return pd.DataFrame(data) if data else pd.DataFrame(columns=KOLOM_KOSONG[nama])


def pastikan_akun():
    """Jika tabel akun kosong, coba isi bagan akun standar aplikasi."""
    data = ambil_semua(lambda: db().table("accounts").select("*").order("kode"))
    if not data:
        db().table("accounts").upsert(AKUN_DEFAULT, on_conflict="kode").execute()
        data = ambil_semua(lambda: db().table("accounts").select("*").order("kode"))
    if not data:
        raise RuntimeError(
            "Tabel public.accounts terbaca kosong. Pastikan SQL schema sudah dijalankan "
            "pada project Supabase yang sama dengan URL di kunci.toml, lalu periksa "
            "Table Editor > accounts."
        )
    kolom = set(data[0].keys())
    wajib = {"kode", "nama", "tipe"}
    if not wajib.issubset(kolom):
        raise RuntimeError(
            "Struktur tabel accounts tidak sesuai. Kolom yang wajib ada: kode, nama, tipe. "
            f"Kolom yang terbaca: {', '.join(sorted(kolom))}"
        )


def rp(x):
    try:
        return "Rp " + f"{float(x or 0):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "Rp 0"


def lines():
    rows = []
    data = ambil_semua(
        lambda: db().table("journal_lines")
        .select("*, journals(tanggal,keterangan,ref_type)")
        .order("id")
    )
    for item in data:
        item = dict(item)
        j = item.pop("journals", None) or {}
        rows.append({**item, **j})
    return pd.DataFrame(
        rows,
        columns=["id", "journal_id", "kode_akun", "debit", "kredit",
                 "tanggal", "keterangan", "ref_type"]
    )


def jurnal(tgl, ket, baris, ref=None):
    """Membuat jurnal berpasangan; total debit harus sama dengan kredit."""
    baris = [(str(a), float(d), float(k)) for a, d, k in baris]
    total_debit = round(sum(x[1] for x in baris), 2)
    total_kredit = round(sum(x[2] for x in baris), 2)
    if total_debit != total_kredit:
        raise ValueError(
            f"Jurnal tidak seimbang: debit {rp(total_debit)}, kredit {rp(total_kredit)}."
        )
    hasil = db().table("journals").insert({
        "tanggal": str(tgl), "keterangan": ket, "ref_type": ref
    }).execute().data
    if not hasil:
        raise RuntimeError("Supabase tidak mengembalikan data jurnal yang baru dibuat.")
    jurnal_id = hasil[0]["id"]
    try:
        db().table("journal_lines").insert([
            {"journal_id": jurnal_id, "kode_akun": a, "debit": d, "kredit": k}
            for a, d, k in baris
        ]).execute()
    except Exception:
        db().table("journals").delete().eq("id", jurnal_id).execute()
        raise


def saldo():
    akun = tbl("accounts")
    if akun.empty:
        raise RuntimeError("Daftar akun kosong. Periksa tabel accounts di Supabase.")
    akun = akun.set_index("kode")
    l = lines()
    if l.empty:
        akun["debit"] = 0.0
        akun["kredit"] = 0.0
    else:
        l[["debit", "kredit"]] = l[["debit", "kredit"]].apply(
            pd.to_numeric, errors="coerce"
        ).fillna(0)
        jumlah = l.groupby("kode_akun")[["debit", "kredit"]].sum()
        akun = akun.join(jumlah).fillna({"debit": 0.0, "kredit": 0.0})
    dk = akun["debit"] - akun["kredit"]
    akun["saldo"] = dk.where(akun["tipe"].isin(["Aset", "Beban"]), -dk)
    return akun


def laba_bersih(a):
    return float(a.loc[a.tipe == "Pendapatan", "saldo"].sum()
                 - a.loc[a.tipe == "Beban", "saldo"].sum())


def go(page, akses=None):
    st.session_state.page = page
    if akses:
        st.session_state.ak = akses


def sudah_susut(key):
    j = tbl("journals")
    return (not j.empty) and (j["ref_type"] == f"susut:{key}").any()


# ------------------------- Dashboard -------------------------
def dashboard():
    st.title("🐟 Dashboard Budidaya Lele")
    a = saldo()
    sm, pb = tbl("stock_moves"), tbl("purchases")
    laba = laba_bersih(a)

    kas = float(a["saldo"].get(KAS, 0))
    persediaan = float(a["saldo"].get("1210", 0) + a["saldo"].get("1220", 0))
    c1, c2, c3 = st.columns(3)
    c1.metric("Jumlah Kas", rp(kas))
    c1.button("Buka Neraca", on_click=go, args=("Akses Cepat", "Neraca"), key="b_kas")
    c2.metric("Profit (Laba/Rugi)", rp(laba), delta="Laba" if laba >= 0 else "Rugi")
    c2.button("Buka Laba Rugi", on_click=go, args=("Akses Cepat", "Laba Rugi"), key="b_laba")
    c3.metric("Total Persediaan", rp(persediaan))
    c3.button("Buka Buku Pembantu", on_click=go, args=("Akses Cepat", "Buku Pembantu"), key="b_stok")

    st.subheader("Persediaan")
    d1, d2 = st.columns(2)
    def stok(k):
        if sm.empty:
            return 0.0
        return float(pd.to_numeric(sm.loc[sm.kategori == k, "qty"], errors="coerce").fillna(0).sum())
    d1.metric("Pakan (kg)", f"{stok('Pakan'):,.1f}", help=f"Nilai {rp(a['saldo'].get('1210', 0))}")
    d2.metric("Bibit (ekor)", f"{stok('Bibit'):,.0f}", help=f"Nilai {rp(a['saldo'].get('1220', 0))}")

    st.subheader("🔔 Reminder")
    ada = False
    if not pb.empty:
        jatuh = pb[(pb.metode == "Utang") & (~pb.lunas.fillna(False))]
        for _, r in jatuh.iterrows():
            if pd.isna(r.get("jatuh_tempo")):
                continue
            sisa = (pd.to_datetime(r.jatuh_tempo).date() - date.today()).days
            teks = f"Utang ke {r.supplier} ({r['item']}) {rp(r.total)} jatuh tempo {r.jatuh_tempo}"
            if sisa < 0:
                st.error(f"TERLAMBAT {-sisa} hari: {teks}")
                ada = True
            elif sisa <= 7:
                st.warning(f"{sisa} hari lagi: {teks}")
                ada = True
    key = date.today().strftime("%Y-%m")
    if not tbl("equipment").empty and not sudah_susut(key):
        st.warning(f"Penyesuaian penyusutan bulan {key} belum dijalankan (menu Peralatan).")
        ada = True
    if not ada:
        st.success("Tidak ada reminder.")

    with st.expander("Setoran modal awal"):
        with st.form("modal", clear_on_submit=True):
            tgl = st.date_input("Tanggal", date.today(), key="modal_tgl")
            nom = st.number_input("Jumlah setoran", min_value=0.0, step=100000.0, key="modal_nom")
            if st.form_submit_button("Simpan setoran modal"):
                if nom > 0:
                    jurnal(tgl, "Setoran modal pemilik", [(KAS, nom, 0), (MODAL, 0, nom)], "modal")
                    st.success("Setoran modal berhasil dicatat.")
                    st.rerun()
                st.warning("Masukkan jumlah lebih dari nol.")


# ------------------------- Pembelian -------------------------
def pembelian():
    st.title("🛒 Pembelian")
    with st.form("beli", clear_on_submit=True):
        c = st.columns(3)
        tgl = c[0].date_input("Tanggal", date.today())
        kat = c[1].selectbox("Kategori", list(AKUN_BELI))
        item = c[2].text_input("Nama barang")
        c = st.columns(4)
        qty = c[0].number_input("Qty", min_value=0.0, step=1.0)
        sat = c[1].text_input("Satuan", "kg")
        harga = c[2].number_input("Harga satuan", min_value=0.0, step=1000.0)
        metode = c[3].selectbox("Pembayaran", ["Tunai", "Utang"])
        supplier = st.text_input("Supplier")
        tempo = st.date_input("Jatuh tempo (jika utang)", date.today())
        submit = st.form_submit_button("Simpan pembelian")
    if submit:
        if not item.strip() or qty <= 0 or harga <= 0:
            st.error("Isi nama barang, qty, dan harga satuan dengan nilai lebih dari nol.")
        else:
            total = qty * harga
            try:
                db().table("purchases").insert({
                    "tanggal": str(tgl), "supplier": supplier, "kategori": kat,
                    "item": item.strip(), "qty": qty, "satuan": sat,
                    "harga": harga, "total": total, "metode": metode,
                    "jatuh_tempo": str(tempo) if metode == "Utang" else None,
                    "lunas": metode == "Tunai"
                }).execute()
                if kat != "Operasional":
                    db().table("stock_moves").insert({
                        "tanggal": str(tgl), "kategori": kat,
                        "item": item.strip(), "qty": qty
                    }).execute()
                kredit = KAS if metode == "Tunai" else UTANG
                jurnal(tgl, f"Beli {item.strip()}",
                       [(AKUN_BELI[kat], total, 0), (kredit, 0, total)], "beli")
                st.success("Pembelian berhasil disimpan.")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menyimpan pembelian: {e}")

    with st.expander("Pemakaian pakan / bibit (kolam)"):
        sm = tbl("stock_moves")
        if sm.empty:
            st.info("Belum ada persediaan.")
        else:
            pasangan = sorted(
                (sm["kategori"].fillna("") + " | " + sm["item"].fillna("")).unique()
            )
            pasangan = [x for x in pasangan if x.strip(" |")]
            if pasangan:
                with st.form("pakai", clear_on_submit=True):
                    tgl_pakai = st.date_input("Tanggal pakai", date.today())
                    pilih = st.selectbox("Item", pasangan)
                    jml = st.number_input("Jumlah dipakai", min_value=0.0, step=1.0)
                    catat = st.form_submit_button("Catat pemakaian")
                if catat:
                    kat_pakai, item_pakai = pilih.split(" | ", 1)
                    tersedia = float(pd.to_numeric(
                        sm.loc[(sm.kategori == kat_pakai) & (sm.item == item_pakai), "qty"],
                        errors="coerce"
                    ).fillna(0).sum())
                    pb_item = tbl("purchases")
                    pb_item = pb_item[
                        (pb_item.kategori == kat_pakai) & (pb_item.item == item_pakai)
                    ]
                    if jml <= 0:
                        st.error("Jumlah pemakaian harus lebih dari nol.")
                    elif jml > tersedia:
                        st.error(f"Stok hanya tersedia {tersedia:g}.")
                    elif pb_item.empty or float(pb_item.qty.sum() or 0) <= 0:
                        st.error("Data pembelian untuk item ini tidak ditemukan.")
                    else:
                        hpp = float(pb_item.total.sum()) / float(pb_item.qty.sum()) * jml
                        try:
                            beban, persed = AKUN_PAKAI[kat_pakai]
                            jurnal(tgl_pakai, f"Pakai {item_pakai}",
                                   [(beban, hpp, 0), (persed, 0, hpp)], "pakai")
                            db().table("stock_moves").insert({
                                "tanggal": str(tgl_pakai), "kategori": kat_pakai,
                                "item": item_pakai, "qty": -jml
                            }).execute()
                            st.success("Pemakaian stok berhasil dicatat.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal mencatat pemakaian: {e}")

    pb = tbl("purchases")
    if not pb.empty:
        belum = pb[(pb.metode == "Utang") & (~pb.lunas.fillna(False))]
        if not belum.empty:
            with st.expander("Bayar utang"):
                opsi = {
                    f"#{r.id} {r.supplier} - {r['item']} - {rp(r.total)}": r
                    for _, r in belum.iterrows()
                }
                pilihan = st.selectbox("Pilih utang", list(opsi))
                if st.button("Tandai lunas (bayar tunai)"):
                    r = opsi[pilihan]
                    try:
                        jurnal(date.today(), f"Bayar utang {r.supplier}",
                               [(UTANG, r.total, 0), (KAS, 0, r.total)], "bayar_utang")
                        db().table("purchases").update({"lunas": True}).eq("id", int(r.id)).execute()
                        st.success("Pembayaran utang berhasil dicatat.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal membayar utang: {e}")
    st.subheader("Transaksi terbaru")
    st.dataframe(
        pb.sort_values("id", ascending=False).head(15) if not pb.empty else pb,
        hide_index=True, use_container_width=True
    )


# ------------------------- Penjualan -------------------------
def penjualan():
    st.title("💰 Penjualan")
    with st.form("jual", clear_on_submit=True):
        c = st.columns(3)
        tgl = c[0].date_input("Tanggal", date.today())
        pembeli = c[1].text_input("Pembeli")
        metode = c[2].selectbox("Pembayaran", ["Tunai", "Piutang"])
        c = st.columns(2)
        kg = c[0].number_input("Berat panen (kg)", min_value=0.0, step=1.0)
        hkg = c[1].number_input("Harga per kg", min_value=0.0, step=500.0)
        submit = st.form_submit_button("Simpan penjualan")
    if submit:
        if kg <= 0 or hkg <= 0:
            st.error("Berat panen dan harga per kg harus lebih dari nol.")
        else:
            total = kg * hkg
            try:
                db().table("sales").insert({
                    "tanggal": str(tgl), "pembeli": pembeli.strip(), "kg": kg,
                    "harga_kg": hkg, "total": total, "metode": metode,
                    "lunas": metode == "Tunai"
                }).execute()
                jurnal(tgl, f"Jual lele ke {pembeli.strip()}",
                       [(KAS if metode == "Tunai" else PIUTANG, total, 0),
                        (JUAL, 0, total)], "jual")
                st.success("Penjualan berhasil disimpan.")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menyimpan penjualan: {e}")

    sl = tbl("sales")
    if not sl.empty:
        belum = sl[~sl.lunas.fillna(False)]
        if not belum.empty:
            with st.expander("Pelunasan piutang"):
                opsi = {
                    f"#{r.id} {r.pembeli} - {rp(r.total)}": r
                    for _, r in belum.iterrows()
                }
                pilihan = st.selectbox("Pilih piutang", list(opsi))
                if st.button("Terima pembayaran"):
                    r = opsi[pilihan]
                    try:
                        jurnal(date.today(), f"Terima piutang {r.pembeli}",
                               [(KAS, r.total, 0), (PIUTANG, 0, r.total)], "terima_piutang")
                        db().table("sales").update({"lunas": True}).eq("id", int(r.id)).execute()
                        st.success("Piutang berhasil dilunasi.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal mencatat pelunasan: {e}")
    st.subheader("Transaksi terbaru")
    st.dataframe(
        sl.sort_values("id", ascending=False).head(15) if not sl.empty else sl,
        hide_index=True, use_container_width=True
    )


# ------------------------- Peralatan -------------------------
def peralatan():
    st.title("🛠️ Peralatan")
    with st.form("alat", clear_on_submit=True):
        c = st.columns(2)
        nama = c[0].text_input("Nama (kolam terpal, pompa, aerator, dll)")
        tgl = c[1].date_input("Tanggal beli", date.today())
        c = st.columns(3)
        harga = c[0].number_input("Harga (dibayar tunai)", min_value=0.0, step=10000.0)
        umur = c[1].number_input("Umur ekonomis (bulan)", min_value=1, value=24)
        residu = c[2].number_input("Nilai residu", min_value=0.0, step=10000.0)
        submit = st.form_submit_button("Simpan peralatan")
    if submit:
        if not nama.strip() or harga <= 0:
            st.error("Nama dan harga peralatan wajib diisi.")
        elif residu > harga:
            st.error("Nilai residu tidak boleh lebih besar dari harga peralatan.")
        else:
            try:
                db().table("equipment").insert({
                    "nama": nama.strip(), "tanggal": str(tgl), "harga": harga,
                    "umur_bulan": int(umur), "residu": residu
                }).execute()
                jurnal(tgl, f"Beli peralatan {nama.strip()}",
                       [("1310", harga, 0), (KAS, 0, harga)], "alat")
                st.success("Peralatan berhasil disimpan.")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menyimpan peralatan: {e}")

    e = tbl("equipment")
    if e.empty:
        st.info("Belum ada peralatan yang dicatat.")
        return
    e["susut_per_bulan"] = (e.harga - e.residu) / e.umur_bulan
    st.dataframe(e, hide_index=True, use_container_width=True)
    key = date.today().strftime("%Y-%m")
    if sudah_susut(key):
        st.success(f"Penyusutan {key} sudah dijalankan.")
    elif st.button(f"Jalankan penyusutan {key} ({rp(e.susut_per_bulan.sum())})"):
        total_susut = float(e.susut_per_bulan.sum())
        try:
            jurnal(date.today(), f"Penyusutan peralatan {key}",
                   [("5140", total_susut, 0), ("1311", 0, total_susut)],
                   f"susut:{key}")
            st.success("Penyusutan berhasil dicatat.")
            st.rerun()
        except Exception as ex:
            st.error(f"Gagal menjalankan penyusutan: {ex}")


# ------------------------- Laporan -------------------------
def jurnal_umum():
    l = lines()
    a = tbl("accounts")[["kode", "nama"]]
    if l.empty:
        st.info("Belum ada jurnal.")
        return
    l = l.merge(a, left_on="kode_akun", right_on="kode", how="left")
    st.dataframe(
        l.sort_values(["tanggal", "journal_id"])[
            ["tanggal", "journal_id", "keterangan", "kode_akun",
             "nama", "debit", "kredit"]
        ],
        hide_index=True, use_container_width=True
    )


def buku_besar():
    a = tbl("accounts")
    if a.empty:
        st.info("Daftar akun belum tersedia.")
        return
    pilihan_akun = st.selectbox("Akun", (a.kode + " - " + a.nama).tolist())
    x = lines()
    if x.empty:
        st.info("Belum ada transaksi jurnal.")
        return
    x = x[x.kode_akun == pilihan_akun.split(" - ")[0]].sort_values(
        ["tanggal", "id"]
    ).copy()
    x[["debit", "kredit"]] = x[["debit", "kredit"]].apply(
        pd.to_numeric, errors="coerce"
    ).fillna(0)
    x["saldo (D-K)"] = (x.debit - x.kredit).cumsum()
    st.dataframe(
        x[["tanggal", "keterangan", "debit", "kredit", "saldo (D-K)"]],
        hide_index=True, use_container_width=True
    )


def buku_pembantu():
    jenis = st.radio(
        "Jenis", ["Utang Usaha", "Piutang Usaha", "Persediaan"],
        horizontal=True
    )
    if jenis == "Utang Usaha":
        p = tbl("purchases")
        u = p[(p.metode == "Utang") & (~p.lunas.fillna(False))] if not p.empty else p
        st.dataframe(
            u.groupby("supplier").total.sum().reset_index() if not u.empty else u,
            hide_index=True
        )
        st.dataframe(u, hide_index=True, use_container_width=True)
    elif jenis == "Piutang Usaha":
        s = tbl("sales")
        u = s[~s.lunas.fillna(False)] if not s.empty else s
        st.dataframe(
            u.groupby("pembeli").total.sum().reset_index() if not u.empty else u,
            hide_index=True
        )
        st.dataframe(u, hide_index=True, use_container_width=True)
    else:
        sm = tbl("stock_moves")
        if sm.empty:
            st.info("Belum ada pergerakan stok.")
        else:
            st.dataframe(
                sm.groupby(["kategori", "item"]).qty.sum().reset_index(),
                hide_index=True
            )
            st.caption("Kartu stok")
            st.dataframe(sm, hide_index=True, use_container_width=True)


def neraca():
    a = saldo().reset_index()
    laba = laba_bersih(a.set_index("kode"))
    aset = a[a.tipe == "Aset"][["kode", "nama", "saldo"]]
    pas = a[a.tipe.isin(["Kewajiban", "Ekuitas"])][["kode", "nama", "saldo"]]
    pas = pd.concat([
        pas,
        pd.DataFrame([{"kode": "-", "nama": "Laba Berjalan", "saldo": laba}])
    ], ignore_index=True)
    c1, c2 = st.columns(2)
    c1.subheader("Aset")
    c1.dataframe(aset, hide_index=True, use_container_width=True)
    c1.metric("Total Aset", rp(aset.saldo.sum()))
    c2.subheader("Kewajiban & Ekuitas")
    c2.dataframe(pas, hide_index=True, use_container_width=True)
    c2.metric("Total Kewajiban + Ekuitas", rp(pas.saldo.sum()))


def laba_rugi():
    a = saldo().reset_index()
    for tipe in ["Pendapatan", "Beban"]:
        x = a[a.tipe == tipe][["kode", "nama", "saldo"]]
        st.subheader(tipe)
        st.dataframe(x, hide_index=True, use_container_width=True)
        st.write(f"Total {tipe}: **{rp(x.saldo.sum())}**")
    st.metric("Laba / (Rugi) Bersih", rp(laba_bersih(a.set_index("kode"))))


def akses_cepat():
    st.title("⚡ Akses Cepat")
    pilih = st.radio("Laporan", AKSES, horizontal=True, key="ak")
    {
        "Jurnal Umum": jurnal_umum,
        "Buku Besar": buku_besar,
        "Buku Pembantu": buku_pembantu,
        "Neraca": neraca,
        "Laba Rugi": laba_rugi,
    }[pilih]()


# ------------------------- Router utama -------------------------
def main():
    st.sidebar.title("Lele Segar")
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"
    st.sidebar.radio("Menu", PAGES, key="page")

    try:
        # Tes koneksi dan pastikan daftar akun ada sebelum menampilkan halaman.
        pastikan_akun()
        halaman = {
            "Dashboard": dashboard,
            "Pembelian": pembelian,
            "Penjualan": penjualan,
            "Peralatan": peralatan,
            "Akses Cepat": akses_cepat,
        }
        halaman[st.session_state.page]()
    except Exception as e:
        st.error("Aplikasi belum dapat memuat data dari Supabase.")
        st.exception(e)
        st.info(
            "Periksa file kunci.toml: SUPABASE_URL dan SUPABASE_KEY harus berasal "
            "dari project Supabase yang sama. Pastikan juga seluruh tabel pada SQL "
            "schema sudah dibuat dan API Data pada project tersebut aktif."
        )


if __name__ == "__main__":
    main()
