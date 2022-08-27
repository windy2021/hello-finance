import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    data = []
    info = {}
    grand_total = 0
    all_stocks_own = db.execute("SELECT DISTINCT stock_symbol FROM transactions WHERE user_id = '" + str(session.get("user_id")) + "'")
    if all_stocks_own:
        for row in all_stocks_own:
            result = lookup(row["stock_symbol"])
            stock_current_price = float(result["price"])
            str_buy = (db.execute("SELECT SUM(share_amount) AS buy FROM transactions WHERE transaction_type = 'BUY' AND user_id = '" + str(session.get("user_id")) + "'" + " AND stock_symbol = '" + row["stock_symbol"] + "'"))[0]['buy']
            if not str_buy:
                str_buy = "0"
            int_buy = int(str_buy)
            str_sell = (db.execute("SELECT SUM(share_amount) AS sell FROM transactions WHERE transaction_type = 'SELL' AND user_id = '" + str(session.get("user_id")) + "'" + " AND stock_symbol = '" + row["stock_symbol"] + "'"))[0]['sell']
            if not str_sell:
                str_sell = "0"
            int_sell = int(str_sell)
            stock_info = {"stock_symbol": row["stock_symbol"], "stock_name": result["name"], "shares": str(int_buy - int_sell), "price": usd(stock_current_price), "total": usd((int_buy - int_sell) * stock_current_price)}

            if int(stock_info["shares"]) > 0:
                data.append(stock_info)
                grand_total = grand_total + ((int_buy - int_sell) * stock_current_price)

    str_current_cash = db.execute("SELECT cash from users where id = '" + str(session.get("user_id")) + "'")[0]["cash"]
    grand_total = grand_total + float(str_current_cash)

    info = {"cash": usd(float(str_current_cash)), "grand_total": usd(grand_total)}

    # print(data)
    return render_template("index.html", data = data, info = info)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology ("must provide symbol")

        result = lookup(request.form.get("symbol"))

        if not result:
            return apology("symbol not found")

        if not request.form.get("shares").isnumeric():
            return apology("not a number", 400)

        if int(request.form.get("shares")) <= 0 or (int(request.form.get("shares"))) % 1 != 0:
            return apology("negative or fractional", 400)

        shares_to_buy = float(request.form.get("shares"))
        query_current_cash = db.execute("SELECT cash from users where id = '" + str(session.get("user_id")) + "'")
        current_cash = float(query_current_cash[0]["cash"])
        stock_price = float(result["price"])

        if ((shares_to_buy * stock_price) > current_cash):
            return apology("you dont have enough cash")

        query_insert_transaction_buy = "INSERT INTO transactions(transaction_type, stock_symbol, stock_price, share_amount, transaction_amount, user_id, transaction_date)" + " VALUES('BUY', '"+ request.form.get("symbol").upper() +"', '"+ str(stock_price) +"', '"+ request.form.get("shares") + "', '" + str(shares_to_buy * stock_price) + "', '"+ str(session.get("user_id")) + "', datetime('now', 'localtime'))"

        if (db.execute(query_insert_transaction_buy) > 0):
            query_update_cash = "UPDATE users SET cash = '" + str(current_cash - (shares_to_buy * stock_price))  + "' WHERE id = '" + str(session.get("user_id")) + "'"
            db.execute(query_update_cash)

            return redirect("/")

    return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    data = db.execute("SELECT * FROM transactions WHERE user_id = '" + str(session.get("user_id")) + "'")
    return render_template("history.html", data = data)

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Show history of transactions"""
    if request.method == "POST":
        if not request.form.get("deposit"):
            return apology ("must provide deposit amount")

        float_deposit = float(request.form.get("deposit"))

        query_current_cash = db.execute("SELECT cash FROM users WHERE id = '" + str(session.get("user_id")) + "'")
        float_current_cash = float(query_current_cash[0]["cash"])

        db.execute("UPDATE users SET cash = '" + str(float_deposit + float_current_cash) + "'")

        return redirect("/")
    return render_template("deposit.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology ("must provide symbol")
        result = lookup(request.form.get("symbol"))
        if result != None:
            price = usd(float(result["price"]))
            return render_template("quote.html", data=result, price = price)
        else:
            return apology("symbol not found")
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        """Register user"""
        if not request.form.get("username"):
            return apology("must provide username", 400)

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) != 0:
            return apology("username already exists", 400)

        if not request.form.get("password") or not request.form.get("confirmation"):
            return apology("must provide password", 400)

        if request.form.get("password") != request.form.get("confirmation"):
            return apology("password not matched", 400)

        pwd = generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8)

        insertQuery = "INSERT INTO users(username, hash) VALUES('" + request.form.get("username") + "', '" + pwd + "') "
        db.execute(insertQuery)

        return redirect("/login")
    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol")
        result = lookup(request.form.get("symbol"))

        if not result:
            return apology("symbol not found")

        if float(request.form.get("shares")) <= 0:
            return apology("shares must be greater than 0")

        stock_price = result["price"]
        shares_to_sell = float(request.form.get("shares"))

        shares_own = 0
        str_buy = (db.execute("SELECT SUM(share_amount) AS buy FROM transactions WHERE transaction_type = 'BUY' AND user_id = '" +
                    str(session.get("user_id")) + "'" + " AND stock_symbol = '" + result["symbol"] + "'"))[0]['buy']
        if not str_buy:
            str_buy = "0"
        int_buy = int(str_buy)
        str_sell = (db.execute("SELECT SUM(share_amount) AS sell FROM transactions WHERE transaction_type = 'SELL' AND user_id = '" +
                    str(session.get("user_id")) + "'" + " AND stock_symbol = '" + result["symbol"] + "'"))[0]['sell']
        if not str_sell:
            str_sell = "0"
        int_sell = int(str_sell)
        shares_own = int_buy - int_sell
        if shares_own < shares_to_sell:
            return apology("you do not own that many shares of the stock")

        query_current_cash = db.execute("SELECT cash from users where id = '" + str(session.get("user_id")) + "'")
        current_cash = float(query_current_cash[0]["cash"])
        query_insert_transaction_buy = "INSERT INTO transactions(transaction_type, stock_symbol, stock_price, share_amount, transaction_amount, user_id, transaction_date)" + " VALUES('SELL', '" + request.form.get(
                                        "symbol").upper() +"', '" + str(stock_price) + "', '" + request.form.get("shares") + "', '" + str(shares_to_sell * stock_price) + "', '"+ str(session.get("user_id")) + "', datetime('now', 'localtime'))"

        if (db.execute(query_insert_transaction_buy) > 0):
            query_update_cash = "UPDATE users SET cash = '" + str(current_cash + (shares_to_sell * stock_price)) + "' WHERE id = '" + str(session.get("user_id")) + "'"
            db.execute(query_update_cash)

            return redirect("/")
    data = get_all_stock()
    return render_template("sell.html", data=data)


def get_all_stock():
    data = []
    all_stocks_own = db.execute("SELECT DISTINCT stock_symbol FROM transactions WHERE user_id = '" + str(session.get("user_id")) + "'")
    if all_stocks_own:
        for row in all_stocks_own:
            result = lookup(row["stock_symbol"])
            stock_current_price = float(result["price"])
            str_buy = (db.execute("SELECT SUM(share_amount) AS buy FROM transactions WHERE transaction_type = 'BUY' AND user_id = '" + str(session.get("user_id")) + "'" + " AND stock_symbol = '" + row["stock_symbol"] + "'"))[0]['buy']
            if not str_buy:
                str_buy = "0"
            int_buy = int(str_buy)
            str_sell = (db.execute("SELECT SUM(share_amount) AS sell FROM transactions WHERE transaction_type = 'SELL' AND user_id = '" + str(session.get("user_id")) + "'" + " AND stock_symbol = '" + row["stock_symbol"] + "'"))[0]['sell']
            if not str_sell:
                str_sell = "0"
            int_sell = int(str_sell)
            stock_info = {"stock_symbol": row["stock_symbol"], "stock_name": result["name"], "shares": str(int_buy - int_sell), "price": usd(stock_current_price), "total": usd((int_buy - int_sell) * stock_current_price)}
            if int(stock_info["shares"]) > 0:
                data.append(stock_info)
    return data
