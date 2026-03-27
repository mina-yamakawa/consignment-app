from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "itaku_SecretKey_Consignment2026"

app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

def get_db_connection():
    conn = sqlite3.connect("database/database.db")
    conn.row_factory = sqlite3.Row 
    return conn

@app.route("/login", methods=["GET", "POST"])
def login():

    # すでにログイン済ならダッシュボードへ
    if session.get("login"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if username == "itaku" and password == "itaku2026":
            session["login"] = True
            return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# トップ
@app.route("/")
def index():

    if session.get("login"):
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# ダッシュボード
@app.route("/dashboard")
def dashboard():

    if not session.get("login"):
        return redirect(url_for("login"))

    conn = get_db_connection()

    month = request.args.get("month")
    if not month:
        month = datetime.now().strftime("%Y-%m")

    today = datetime.now().strftime("%Y-%m-%d")


    res = conn.execute(
        "SELECT SUM(amount) as total FROM sales WHERE strftime('%Y-%m', sale_date) = ?",
        (month,)
    ).fetchone()

    total_sales = int(res["total"]) if res and res["total"] else 0


    res = conn.execute(
        "SELECT SUM(amount) as total FROM sales WHERE sale_date = ?",
        (today,)
    ).fetchone()

    today_total = int(res["total"]) if res and res["total"] else 0


    res = conn.execute("""
        SELECT SUM(s.amount * (p.fee_rate / 100.0)) as total
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE p.category = 'fee'
        AND strftime('%Y-%m', s.sale_date) = ?
    """, (month,)).fetchone()

    fee_income = int(res["total"]) if res and res["total"] else 0


    res = conn.execute("""
        SELECT SUM(s.amount - (p.cost_price * s.quantity)) as profit
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE p.category = 'buy'
        AND strftime('%Y-%m', s.sale_date) = ?
    """, (month,)).fetchone()

    buy_profit = int(res["profit"]) if res and res["profit"] else 0


    settings = conn.execute(
        "SELECT rental_income, expense FROM monthly_settings WHERE month = ?",
        (month,)
    ).fetchone()

    rental_income = 0
    expense = 0

    if settings:
        if settings["rental_income"]:
            rental_income = int(settings["rental_income"])

        if settings["expense"]:
            expense = int(settings["expense"])


    final_profit = fee_income + buy_profit + rental_income - expense


    low_stocks = conn.execute("""
        SELECT p.name,
        (IFNULL(st.total_in,0) - IFNULL(sa.total_out,0)) as stock
        FROM products p
        LEFT JOIN (
            SELECT product_id, SUM(quantity) as total_in
            FROM stock_entries GROUP BY product_id
        ) st ON p.id = st.product_id
        LEFT JOIN (
            SELECT product_id, SUM(quantity) as total_out
            FROM sales GROUP BY product_id
        ) sa ON p.id = sa.product_id
        GROUP BY p.id
        HAVING stock <= 3
    """).fetchall()


    expiring = conn.execute("""
        SELECT p.name, se.expiry_date
        FROM stock_entries se
        JOIN products p ON se.product_id = p.id
        WHERE se.expiry_date IS NOT NULL
        AND se.expiry_date != ''
        ORDER BY se.expiry_date ASC
        LIMIT 5
    """).fetchall()


    conn.close()


    return render_template(
        "dashboard.html",
        month=month,
        total_sales=total_sales,
        today_total=today_total,
        fee_income=fee_income,
        buy_profit=buy_profit,
        rental_income=rental_income,
        expense=expense,
        final_profit=final_profit,
        low_stocks=low_stocks,
        expiring=expiring
    )

@app.route("/monthly", methods=["GET", "POST"])
def monthly():

    conn = get_db_connection()

    month = request.args.get("month")

    if not month:
        month = datetime.now().strftime("%Y-%m")


    if request.method == "POST":

        rental_income = request.form.get("rental_income")
        expense = request.form.get("expense")

        conn.execute("""
            DELETE FROM monthly_settings
            WHERE month = ?
        """, (month,))

        conn.execute("""
            INSERT INTO monthly_settings
            (month, rental_income, expense)
            VALUES (?, ?, ?)
        """, (month, rental_income, expense))

        conn.commit()


    data = conn.execute("""
        SELECT *
        FROM monthly_settings
        WHERE month = ?
    """, (month,)).fetchone()


    conn.close()


    return render_template(
        "monthly.html",
        month=month,
        data=data
    )



# 委託者一覧
@app.route("/consignors")
def consignors():
    if not session.get("login"):
        return redirect(url_for("login"))
    
    conn = get_db_connection()
    consignors = conn.execute("SELECT * FROM consignors").fetchall()
    conn.close()
    return render_template("consignors.html", consignors=consignors or [])

# 委託者追加
@app.route("/consignors/add", methods=["GET", "POST"])
def add_consignor():

    if request.method == "POST":
        name = request.form.get("name")
        sns_url = request.form.get("sns_url")
        memo = request.form.get("memo")

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO consignors (name, sns_url, memo) VALUES (?, ?, ?)",
            (name, sns_url, memo)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("consignors"))

    return render_template("add_consignor.html")

@app.route("/consignors/edit/<int:id>", methods=["GET", "POST"])
def edit_consignor(id):

    conn = get_db_connection()

    consignor = conn.execute(
        "SELECT * FROM consignors WHERE id = ?",
        (id,)
    ).fetchone()

    if request.method == "POST":

        name = request.form.get("name")
        sns_url = request.form.get("sns_url")
        memo = request.form.get("memo")

        conn.execute(
            "UPDATE consignors SET name=?, sns_url=?, memo=? WHERE id=?",
            (name, sns_url, memo, id)
        )

        conn.commit()
        conn.close()

        return redirect(url_for("consignors"))

    conn.close()

    return render_template(
        "edit_consignor.html",
        consignor=consignor
    )

@app.route("/consignors/delete/<int:id>", methods=["POST"])
def delete_consignor(id):

    conn = get_db_connection()

    # 商品取得
    products = conn.execute(
        "SELECT id FROM products WHERE consignor_id = ?",
        (id,)
    ).fetchall()

    for p in products:

        conn.execute(
            "DELETE FROM stock_entries WHERE product_id = ?",
            (p["id"],)
        )

        conn.execute(
            "DELETE FROM sales WHERE product_id = ?",
            (p["id"],)
        )

    conn.execute(
        "DELETE FROM products WHERE consignor_id = ?",
        (id,)
    )

    conn.execute(
        "DELETE FROM consignors WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("consignors"))


# 商品一覧
@app.route("/products")
def products():
    if not session.get("login"):
        return redirect(url_for("login"))
    
    conn = get_db_connection()

    rows = conn.execute("""
        SELECT 
            p.id, p.name, p.price, p.category, p.cost_price, p.fee_rate,
            c.name as consignor_name,
            IFNULL(st.total_in, 0) as total_in,
            
            -- 売上が入荷数を超えていたら「入荷数」を表示、そうでなければ「売上数」を表示
            CASE 
                WHEN IFNULL(sa.total_out, 0) > IFNULL(st.total_in, 0) THEN IFNULL(st.total_in, 0)
                ELSE IFNULL(sa.total_out, 0) 
            END as display_total_out,

            -- 在庫計算（入荷 - 売上）。マイナスなら0にする
            MAX(0, (IFNULL(st.total_in, 0) - IFNULL(sa.total_out, 0))) as current_stock
        FROM products p
        LEFT JOIN consignors c ON p.consignor_id = c.id
        LEFT JOIN (
            SELECT product_id, SUM(quantity) as total_in 
            FROM stock_entries GROUP BY product_id
        ) st ON p.id = st.product_id
        LEFT JOIN (
            SELECT product_id, SUM(quantity) as total_out 
            FROM sales GROUP BY product_id
        ) sa ON p.id = sa.product_id
        ORDER BY p.id DESC
    """).fetchall()

    conn.close()

    products_list = []
    for r in rows:
        profit = 0
        if r["category"] == "buy" and r["cost_price"]:
            profit = int(r["price"]) - int(r["cost_price"])
        elif r["category"] == "fee" and r["fee_rate"]:
            profit = int(r["price"]) * (float(r["fee_rate"]) / 100.0)

        products_list.append({
            "id": r["id"],
            "name": r["name"],
            "price": r["price"],
            "consignor_name": r["consignor_name"],
            "profit": int(profit),
            "total_in": r["total_in"],
            "total_out": r["display_total_out"], 
            "current_stock": r["current_stock"]
        })

    return render_template("products.html", products=products_list)


# 商品追加
@app.route("/products/add", methods=["GET", "POST"])
def add_product():

    conn = get_db_connection()
    consignors = conn.execute("SELECT * FROM consignors").fetchall()
    conn.close()

    if request.method == "POST":

        name = request.form.get("name")
        price = request.form.get("price")
        consignor_id = request.form.get("consignor_id")

        category = request.form.get("category")
        cost_price = request.form.get("cost_price")
        fee_rate = request.form.get("fee_rate")
        fee_description = request.form.get("fee_description")
        memo = request.form.get("memo")


        if category == "buy":
            fee_rate = None
            fee_description = None

        elif category == "fee":
            cost_price = None
            if not price:
                price = 0


        if name and consignor_id:

            conn = get_db_connection()

            conn.execute("""
                INSERT INTO products
                (name, price, consignor_id, category, cost_price, fee_rate, fee_description, memo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                price,
                consignor_id,
                category,
                cost_price,
                fee_rate,
                fee_description,
                memo
            ))

            conn.commit()
            conn.close()

            return redirect(url_for("products"))

    return render_template("add_product.html", consignors=consignors)

# 商品編集
@app.route("/products/edit/<int:id>", methods=["GET", "POST"])
def edit_product(id):
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (id,)).fetchone()
    consignors = conn.execute("SELECT * FROM consignors").fetchall()

    if product is None:
        conn.close()
        return redirect(url_for("products"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price = request.form.get("price", "").strip()
        consignor_id = request.form.get("consignor_id", None)

        if name and price and consignor_id:
            conn.execute(
                "UPDATE products SET name=?, price=?, consignor_id=? WHERE id=?",
                (name, price, consignor_id, id)
            )
            conn.commit()
            conn.close()
            return redirect(url_for("products"))

    conn.close()
    return render_template("edit_product.html", product=product, consignors=consignors or [])

# 商品削除
@app.route("/products/delete/<int:id>", methods=["POST"])
def delete_product(id):

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM products WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("products"))


# 入荷一覧表示
@app.route("/stock_entries")
def stock_entries():
    if not session.get("login"):
        return redirect(url_for("login"))
    
    conn = get_db_connection()
  
    stock_entries = conn.execute("""
        SELECT s.id,
            p.name AS product_name,
            s.quantity,
            s.arrival_date,
            s.expiry_date,
            c.name AS consignor_name
        FROM stock_entries s
        JOIN products p ON s.product_id = p.id
        LEFT JOIN consignors c ON p.consignor_id = c.id
        ORDER BY
            s.expiry_date IS NULL,
            s.expiry_date ASC
        """).fetchall()    
    conn.close()
    return render_template("stock_entries.html", stock_entries=stock_entries or [])

# 入荷追加フォーム
@app.route("/stock_entries/add")
def add_stock_entries():
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()

    if request.method == "POST":
        product_id = request.form.get("product_id")
        quantity = request.form.get("quantity")
        arrival_date = request.form.get("arrival_date")
        expiry_date = request.form.get("expiry_date") or None

        if product_id and quantity and arrival_date:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO stock_entries (product_id, quantity, arrival_date, expiry_date) VALUES (?, ?, ?, ?)",
                (product_id, quantity, arrival_date, expiry_date)
            )
            conn.commit()
            conn.close()
            return redirect(url_for("stock_entries"))

    return render_template("add_stock.html", products=products or [])

@app.route("/stock_entries/add", methods=["GET", "POST"])
def add_stock_entry():
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products").fetchall()

    if request.method == "POST":
        product_id = request.form["product_id"]
        quantity = request.form["quantity"]
        arrival_date = request.form["arrival_date"]
        expiry_date = request.form["expiry_date"]

        conn.execute(
            "INSERT INTO stock_entries (product_id, quantity, arrival_date, expiry_date) VALUES (?, ?, ?, ?)",
            (product_id, quantity, arrival_date, expiry_date)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("stocks"))

    conn.close()
    return render_template("add_stock_entry.html", products=products)

# 入荷編集機能
@app.route("/stock_entries/edit/<int:id>", methods=["GET", "POST"])
def edit_stock_entry(id):
    conn = get_db_connection()

    if request.method == "POST":
        quantity = request.form["quantity"]
        arrival_date = request.form["arrival_date"]
        expiry_date = request.form["expiry_date"]

        conn.execute("""
            UPDATE stock_entries
            SET quantity = ?, arrival_date = ?, expiry_date = ?
            WHERE id = ?
        """, (quantity, arrival_date, expiry_date, id))

        conn.commit()
        conn.close()
        return redirect(url_for("stock_entries"))

    stock = conn.execute(
        "SELECT * FROM stock_entries WHERE id = ?", (id,)
    ).fetchone()
    conn.close()

    return render_template("edit_stock.html", stock=stock)

# 入荷削除機能
@app.route("/stock_entries/delete/<int:id>", methods=["POST"])
def delete_stock_entry(id):
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM stock_entries WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("stock_entries"))

# 売上一覧ページ
@app.route("/sales")
def sales():
    if not session.get("login"):
        return redirect(url_for("login"))
    
    conn = get_db_connection()

    sales = conn.execute("""
    SELECT
        s.id,
        p.name,
        s.quantity,
        s.amount,
        s.sale_date,
        p.category,
        p.cost_price,
        CASE 
            WHEN p.category = 'fee' THEN CAST(s.amount * (IFNULL(p.fee_rate, 0) / 100.0) AS INTEGER)
            WHEN p.category = 'buy' THEN CAST(s.amount - (IFNULL(p.cost_price, 0) * s.quantity) AS INTEGER)
            ELSE 0 
        END as profit
    FROM sales s
    LEFT JOIN products p ON s.product_id = p.id
    ORDER BY s.sale_date DESC, s.id DESC
    """).fetchall()
    conn.close()
    return render_template("sales.html", sales=sales)

# 売上登録ページ
@app.route("/sales/add", methods=["GET", "POST"])
def add_sale():
    conn = get_db_connection()

    if request.method == "POST":
        product_id = request.form.get("product_id")
        quantity = int(request.form.get("quantity"))
        sale_date = request.form.get("sale_date")

        stock_info = conn.execute("""
            SELECT (IFNULL(st.total_in, 0) - IFNULL(sa.total_out, 0)) as current_stock
            FROM products p
            LEFT JOIN (SELECT product_id, SUM(quantity) as total_in FROM stock_entries GROUP BY product_id) st ON p.id = st.product_id
            LEFT JOIN (SELECT product_id, SUM(quantity) as total_out FROM sales GROUP BY product_id) sa ON p.id = sa.product_id
            WHERE p.id = ?
        """, (product_id,)).fetchone()

        if stock_info and stock_info["current_stock"] < quantity:
            return "エラー：在庫が足りません！ (現在の在庫: " + str(stock_info["current_stock"]) + ")"

        product = conn.execute("SELECT price FROM products WHERE id = ?", (product_id,)).fetchone()
        amount = product["price"] * quantity
        conn.execute("INSERT INTO sales (product_id, quantity, amount, sale_date) VALUES (?, ?, ?, ?)",
                     (product_id, quantity, amount, sale_date))
        conn.commit()
        conn.close()
        return redirect(url_for('sales'))

    products = conn.execute("""
        SELECT p.id, p.name, p.price,
               (IFNULL(st.total_in, 0) - IFNULL(sa.total_out, 0)) as current_stock
        FROM products p
        LEFT JOIN (SELECT product_id, SUM(quantity) as total_in FROM stock_entries GROUP BY product_id) st ON p.id = st.product_id
        LEFT JOIN (SELECT product_id, SUM(quantity) as total_out FROM sales GROUP BY product_id) sa ON p.id = sa.product_id
        WHERE current_stock > 0
    """).fetchall()
    conn.close()
    
    return render_template("add_sale.html", products=products)

# 売上削除
@app.route("/sales/delete/<int:id>", methods=["POST"])
def delete_sale(id):

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM sales WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("sales"))

# 在庫
@app.route("/stocks")
def stocks():
    if not session.get("login"):
        return redirect(url_for("login"))
    
    conn = get_db_connection()

    stocks = conn.execute("""
        SELECT
            p.name,
            c.name AS consignor_name,

            se.expiry_date,

            COALESCE(SUM(se.quantity), 0) AS total_in,
            COALESCE(SUM(sa.quantity), 0) AS total_out,

            COALESCE(SUM(se.quantity), 0) -
            COALESCE(SUM(sa.quantity), 0) AS stock

        FROM products p

        LEFT JOIN consignors c
        ON p.consignor_id = c.id

        LEFT JOIN stock_entries se
        ON p.id = se.product_id

        LEFT JOIN sales sa
        ON p.id = sa.product_id

        GROUP BY
            p.id,
            se.expiry_date

        ORDER BY
            se.expiry_date

        """).fetchall()

    conn.close()

    return render_template("stocks.html", stocks=stocks)



@app.route("/expiry")
def expiry():
    conn = get_db_connection()
    items = conn.execute("""
        SELECT p.name, se.expiry_date
        FROM stock_entries se
        JOIN products p ON se.product_id = p.id
        WHERE se.expiry_date IS NOT NULL
        AND se.expiry_date <= date('now', '+3 days')
    """).fetchall()
    conn.close()
    return render_template("expiry.html", items=items)

# 委託者別の支払い（精算）まとめ画面
@app.route("/settlements")
def settlements():
    conn = get_db_connection()
    month = request.args.get("month") or datetime.now().strftime("%Y-%m")

    rows = conn.execute("""
        SELECT 
            c.name as consignor_name,
            SUM(s.amount) as total_sales,
            SUM(CAST(s.amount * (IFNULL(p.fee_rate, 0) / 100.0) AS INTEGER)) as total_profit,
            MAX(s.settled_date) as settled_day
        FROM sales s
        JOIN products p ON s.product_id = p.id
        JOIN consignors c ON p.consignor_id = c.id
        WHERE strftime('%Y-%m', s.sale_date) = ? 
          AND p.category = 'fee'
        GROUP BY c.id
    """, (month,)).fetchall()

    settlement_data = []
    total_payment_sum = 0
    total_fee_sum = 0

    for r in rows:
        sales_val = r["total_sales"] or 0
        profit_val = r["total_profit"] or 0
        payment_val = sales_val - profit_val
        
        settlement_data.append({
            "consignor_name": r["consignor_name"],
            "total_sales": sales_val,
            "total_fee": profit_val,
            "net_payment": payment_val,
            "is_settled": r["settled_day"] is not None,
            "settled_date": r["settled_day"]
        })
        
        total_payment_sum += payment_val
        total_fee_sum += profit_val

    conn.close()
    
    today_date = datetime.now().strftime("%Y-%m-%d")

    return render_template(
        "settlements.html",
        month=month,
        settlement_data=settlement_data,
        total_payment_sum=total_payment_sum,
        total_fee_sum=total_fee_sum,
        today_date=today_date
    )

@app.route("/settlements/update_status", methods=["POST"])
def update_settlement_status():
    month = request.form.get("month")
    consignor_name = request.form.get("consignor_name")
    status = request.form.get("status")
    input_date = request.form.get("settled_date")

    if status == "paid":
        final_date = input_date if input_date and input_date.strip() != "" else datetime.now().strftime("%Y-%m-%d")
    else:
        final_date = None

    conn = get_db_connection()
    conn.execute("""
        UPDATE sales
        SET settled_date = ?
        WHERE strftime('%Y-%m', sale_date) = ?
          AND product_id IN (
              SELECT p.id FROM products p 
              JOIN consignors c ON p.consignor_id = c.id
              WHERE c.name = ? AND p.category = 'fee'
          )
    """, (final_date, month, consignor_name))
    conn.commit()
    conn.close()
    
    return redirect(url_for('settlements', month=month))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
