import os
import copy
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, get_date

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


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
 # iterate through purchases table where user_id = session.get(userid)./
 # copy dictionary into another dictionary, and if row['name'] is already in new dictionary, volume is added. (only do name and volume)
 # once done, we need current pricing data, so for rows in dict, lookup(name), and replace price with current price.
 # then, and only then, iterate through the dict assigning volume * value to total.

    data = db.execute("SELECT volume, stock FROM purchases WHERE user_id = ?", session["user_id"] )

    sorted_data = {}
    testing_list = []
    # nested dictionary see new_item for format
    for row in data:
        stock = row['stock']
        volume = int((row['volume']))
        if stock in sorted_data:
            sorted_data[stock]["volume"] += volume
        else:
            new_item = {"volume": volume, "price": 0, "total": 0}
            testing_list.append(new_item)
            sorted_data[stock] = new_item

            #tsla purchase not being read.

            # midway = copy.deepcopy(sorted_data)

    sale_data =  db.execute("SELECT volume, stock FROM sales WHERE user_id = ?", session["user_id"] )
    for row in sale_data:
        sale_stock = row['stock']
        sale_volume = row['volume']
        if sale_stock in sorted_data:
            sorted_data[sale_stock]["volume"] += sale_volume # note sale db is formatted with negative values for outgoing volume. i.e sale_volume is negative, which is why we add it.



    # add price via lookup
    for key in sorted_data:
        current_price_dict = lookup(key)
        sorted_data[key]["price"] = current_price_dict['price']
    # calculate total
    for key in sorted_data:
        total = float(sorted_data[key]['price']) * float(sorted_data[key]['volume'])
        sorted_data[key]['total'] = total

    dict9000 = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    if not dict9000:
        return redirect("/register")
    balance = int(dict9000[0]['cash'])

    total_portfolio = 0

    for key in sorted_data:
        total_portfolio += sorted_data[key]['total']
    total_portfolio += balance


    return render_template("index.html", data=sorted_data, balance=balance, total_portfolio=total_portfolio, usd=usd, name=get_name(session.get("user_id"))) #sorted_data


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == 'POST':
        if not request.form.get("symbol"):
            return apology("Please enter a Company Symbol")
        elif not request.form.get("shares") or not request.form.get("shares").isdigit():
            return apology("Invalid Share Amount")
        elif int(request.form.get("shares")) <= 0:
            return apology("Share Amount Must be Greater than 0")
        else:
            # deduct cash sum from account
            price_csv = lookup(request.form.get("symbol")) #get csv
            if not price_csv:                                                                # if not price_csv['name'] or  not price_csv['price'] or not price_csv['symbol'] :
                return apology("Unable to complete lookup. Please check symbol.")
            purchase_price = price_csv['price'] #get most recent/current price - this WONT work as you cant index into dicts with numbers. potential fix: list(my_dict.keys())[0] ?
            total = float(purchase_price) * int(request.form.get("shares"))
            #get user from session cookie
            client_id = session.get("user_id") #not sure if user_id and the id in db are the same.
            balance_csv = db.execute("SELECT cash FROM users WHERE id = ?", client_id)
            balance = balance_csv[0]['cash'] #returns a list of dictionaries regardless of the length of the list or dictionary. i.e in this use case its a list of one length with a dictionary of 1 kvp.
            if total > float(balance):
                return apology("Not Enough Funds To Complete Transaction")
            # perform deduction in db
            db.execute("UPDATE users SET cash = (cash - ?) WHERE id = ?", total, client_id)
            # add purchase detail to purchases db (linked by user ID)
            totalfordb = total - (total * 2)
            pricefordb = purchase_price - (purchase_price * 2)
            db.execute("INSERT INTO purchases (user_id, stock, date, volume, price, total) VALUES (?, ?, ?, ?, ?, ?)", client_id, request.form.get("symbol").upper(), get_date(), request.form.get("shares"), pricefordb, totalfordb)

            return redirect("/")
    else: # (if method == GET)
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    purchases = db.execute("SELECT stock, date, volume, price, total FROM purchases WHERE user_id = ?", session.get("user_id"))
    sales = db.execute("SELECT stock, date, volume, price, total FROM sales WHERE user_id = ?", session.get("user_id"))
    testing = purchases + sales

    #bubble sort by datetime

    length = len(testing)

    for i in range(0, length -1, +1):
        for j in range(0, length - i - 1, +1):
            if testing[j]['date'] < testing[j + 1]['date']:
                middleman = testing[j]['date']
                testing[j]['date'] = testing[j + 1]['date']
                testing[j + 1]['date'] = middleman

    for row in testing:
        if row['price'] < 0:
            row['type'] = 'Purchase'
        else:
            row['type'] = 'Sale'
           # row['price'] = (f"+{str(row['price'])}") -> obselete due to distribution $ formatting
           # row['total'] = (f"+{str(row['total'])}")




    return render_template("history.html", testing=testing, user=session.get("user_id"))


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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
            return apology("Please enter a Company Symbol", 400) #check data too
        else:
            data = lookup(request.form.get("symbol"))
            if not data:
                return apology("Stock Not Found", 400)
            return render_template("quotedisplay.html", content=data, usd=usd)
    else: #(if get)
        return render_template("quoterequest.html", usd=usd)


@app.route("/register", methods=["GET", "POST"])
def register():
    session.clear()
    if request.method == 'POST':
        # check user input and render_template apology
        if not request.form.get("username"):
            return apology("Please choose a Username", 400)
        if not request.form.get("password"):
            return apology("Please choose a Password", 400)
        if not request.form.get("confirmation"):
            return apology("Please confirm your Password", 400)
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords must match", 400)
        users = db.execute("SELECT username FROM users")
        for row in users:
            if row['username'].upper() == request.form.get("username").upper():
                return apology("Username Already Taken", 400)

        else:
            # generate password hash
            hashedpassword = generate_password_hash(request.form.get("password"), method='pbkdf2', salt_length=12)
            # insert into db
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), hashedpassword)
            return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        # find out what is owned
        purchase_data = db.execute("SELECT * FROM purchases WHERE user_id = ?", session.get("user_id"))
        sale_data = db.execute("SELECT * FROM sales WHERE user_id = ?", session.get("user_id"))



        data = purchase_data + sale_data
        sorted_data = {}
        for row in data:
            stock = row['stock']
            volume = int((row['volume']))
            if stock in sorted_data:
                sorted_data[stock] += volume
            else:
                new_value = volume
                sorted_data[stock] = new_value



            # make a list of stocks that have greater than 0 volume
        viable_stocks = []
        for stock in sorted_data:
            if sorted_data[stock] > 0:
                viable_stocks.append(stock)



        return render_template("sell.html", stocks=viable_stocks)
    else:
        # check if account has enough shares of correct stock
        # if check passed
        # get current price of stock, create variable: total = (price * volume)
        # remove volume from user account
        # create purchases entry with negative x volume
        # add total to users->user->cash
        # render template sell_success -> which is just confirmation header and a big fat "/" button.

        amount = int(request.form.get("shares"))
        stock = request.form.get("symbol")

        test = lookup(stock)
        if not test:
            return apology("Stock Lookup Failed", 400)

        purchase_data = db.execute("SELECT * FROM purchases WHERE user_id = ? AND stock = ?", session.get("user_id"), stock)
        sale_data = db.execute("SELECT * FROM sales WHERE user_id = ? AND stock = ?", session.get("user_id"), stock)

        purchase_volume = 0
        for row in purchase_data:
            purchase_volume += row['volume']
        for row in sale_data:
            purchase_volume += row['volume']

        if amount > purchase_volume:
            return apology("Not enough stock")
        else:
            price_sheet = lookup(stock)
            price = price_sheet['price']
            sale_total = float(price) * amount
            data = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))
            balance = data[0]['cash']
            new_balance = balance + sale_total

            amount_withdrawn = (amount - (amount * 2))

            # add to balance
            db.execute("UPDATE users SET cash = ? WHERE id = ?", new_balance, session.get("user_id"))
            # create sale entry in purchases
            db.execute("INSERT INTO sales (user_id, stock, date, volume, price, total) VALUES (?, ?, ?, ?, ?, ?)", session.get("user_id"), stock.upper(), get_date(), amount_withdrawn, price, sale_total)

            message = (f"You sold {amount} of {stock.upper()} at {price}.")


            # return render_template("sellsuccess.html", message=message) obselete due to check50 / specifications
            return redirect("/")


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "GET":
        return render_template("deposit.html")
    else: # if post
        m = request.form.get("amount")
        if not m:
            return apology("Please Enter An Amount To Deposit")
        elif not m.isdigit():
            return apology("Please Enter A Valid Amount")
        # checks done
        info = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))
        amt = info[0]['cash']
        new_amt = amt + int(m)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_amt, session.get("user_id"))

        return redirect("/")


def get_name(name):
    n = db.execute("SELECT username FROM users WHERE id = ?", name)
    if not n:
        return None
    else:
        return n[0]['username']



# issue, buying and selling stocks skyrockets portfolio value, meaning either buy value is too cheap or sell value is too high.



