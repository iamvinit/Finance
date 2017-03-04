#from cs50 import SQL
import sqlite3,sys
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database


@app.route("/")
@login_required
def index():
    db = sqlite3.connect("finance.db")
    cursor = db.execute('''
        SELECT name, symbol , sum(
        CASE
        WHEN type = 'buy'
        THEN numofshares
        ELSE -numofshares
        END),
        price

        FROM purchases,shares
        WHERE userid = (?) AND purchases.shareid = shares.shareid
        GROUP BY 
        purchases.shareid

    ''',(session["user_id"], ))

    rows = cursor.fetchall()
    cursor = db.execute("SELECT cash FROM users where id = (?)",(session["user_id"],))
    cash = cursor.fetchone()[0]
    rows.append(("","CASH","",""))
    cols = list(zip(*rows))

    db.commit()
    db.close()
    #finding total
    total = []
    for x , y in zip(cols[2][:-1],cols[3][:-1]):
        total.append(format(float(x) * float(y), '.2f'))
    total.append(format(cash,'.2f'))

    #finding current price
    curprice = []
    for sym in cols[1][:-1]:
        curprice.append(lookup(sym)["price"])
    curprice.append("")
    #return apology(str(curprice))
    return render_template('index.html',symbol = cols[1],name = cols[0], numshare = cols[2], price = cols[3], total = total,curprice = curprice)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "GET":
        return render_template("buy.html")


    elif request.method =="POST":
        if not request.form.get("stocksymbol"):
            return apology("Enter stock symbol")
        if not request.form.get("numshares").isdigit():
            return apology("Invalid Number of stock")
        db = sqlite3.connect("finance.db")
        result = lookup(request.form.get("stocksymbol"))

        if not result:
            return apology("Invalid Stock Symbol")

        # check if user can afford shares
        cursor = db.execute("SELECT cash FROM users where id = (?)",(session["user_id"],))
        cashleft = cursor.fetchone()[0] - result["price"] * int(request.form.get("numshares"))
        if cashleft < 0:
            return apology("You donot have enough cash to buy the shares")
        else:
            db.execute("UPDATE users SET cash = (?) WHERE id = (?)",(cashleft, session["user_id"]))

        #find the shareid
        cursor = db.execute("SELECT shareid FROM shares where symbol =(?)",(result.get("symbol"),))
        rows = cursor.fetchone()
        if not rows:
            db.execute("INSERT into shares(name,symbol) VALUES (?,?)",(result.get("name"), (result.get("symbol"))))
            cursor = db.execute("SELECT shareid FROM shares where symbol =(?)",(result.get("symbol"),))
            rows = cursor.fetchone()

        shareid = rows[0]

        db.execute("INSERT INTO purchases(userid,shareid,numofshares,price,type) VALUES (?,?,?,?,?)",(session["user_id"], shareid, request.form.get("numshares"), result.get("price"), "buy")  )

        db.commit()
        db.close()

        return redirect(url_for("index"))


@app.route("/history")
@login_required
def history():
    db = sqlite3.connect("finance.db")
    cursor = db.execute("SELECT * FROM purchases,shares WHERE userid =(?) AND purchases.shareid = shares.shareid ORDER BY time ASC",(session["user_id"],))
    rows = cursor.fetchall()
    cols = list(zip(*rows))

    db.commit()
    db.close()
    if rows:
        return render_template("history.html",transno = cols[0], purtype = cols[6], share = cols[8], price = cols[3], numshare = cols[4], time = cols[5] )
    else : 
        return render_template("history.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        db = sqlite3.connect("finance.db")
        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT id , hash FROM users WHERE username =(?)", (request.form.get("username"),))
        row = rows.fetchall()
        #print( row[0][0], file=sys.stderr)
        # ensure username exists and password is correct
        if len(row) != 1 or not pwd_context.verify(request.form.get("password"), row[0][1]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = row[0][0]
        db.close()
        # redirect user to home page
        return redirect(url_for("index"))


    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")

    elif request.method == "POST":
        result = lookup(request.form.get("stocksymbol"))
        if not result:
            return apology("Invalid Stock Symbol")
        else:
            return render_template("quoted.html",**result)


@app.route("/register", methods=["GET", "POST"])
def register():

    session.clear()

    if request.method == "POST":
        db = sqlite3.connect("finance.db")
        if not request.form.get("username"):
            return apology("Must provide username")
        if not request.form.get("password1"):
            return apology("Must provide password")
        if not request.form.get("password2"):
            return apology("Reenter the password")
        if request.form.get("password1") != request.form.get("password2"):
            return apology("Passwords do not match")

        rows = db.execute("SELECT * FROM users WHERE username = (?)",(request.form.get("username"),))

        if len(rows.fetchall()) > 0:
            return apology("Username already taken")

        db.execute("INSERT INTO users(username, hash) VALUES (?,?)", (request.form.get("username"), pwd_context.encrypt(request.form.get("password1"))  ))
        db.commit()
        db.close()
        return redirect(url_for("index"))
    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    db = sqlite3.connect("finance.db")
    cursor = db.execute('''
            SELECT symbol , sum(
            case
            WHEN type = 'buy'
            THEN numofshares
            ELSE -numofshares
            END),purchases.shareid
            FROM purchases,shares
            WHERE userid = (?)  AND purchases.shareid = shares.shareid
            GROUP BY 
            purchases.shareid
        ''',(session["user_id"], ))
    rows = cursor.fetchall()
    cols = list(zip(*rows))
    db.commit()
    db.close()
    if request.method == ("GET"):
        return render_template("sell.html" , sharesym = cols[0])
    if request.method == ("POST"):
        symshare = request.form.get("symshare")
        numshare = request.form.get("numshares")
        if not symshare:
            return apology("Invalid Share Symbol")
        if not numshare.isdigit():
            return apology("Invalid Number of Shares")
        maxshares = cols[1][cols[0].index(symshare)]
        if int(numshare) > maxshares:
            return apology("Max {} shares can be sold ".format(maxshares))
        shareid =  cols[2][cols[0].index(symshare)]

        price = lookup(symshare)["price"]

        db = sqlite3.connect("finance.db")
        cursor = db.execute("SELECT cash FROM users where id = (?)",(session["user_id"],))
        cashleft = cursor.fetchone()[0] + int(price) * int(numshare)
        db.execute("UPDATE users SET cash = (?) WHERE id = (?)",(cashleft, session["user_id"]))

        db.execute("INSERT INTO purchases(userid,shareid,numofshares,price,type) VALUES (?,?,?,?,?)",(session["user_id"], shareid, numshare, price, "sell")  )
        db.commit()
        db.close()

        return redirect(url_for("index"))



 