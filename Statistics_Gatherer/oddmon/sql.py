import logging
import sqlite3 as lite

logger = logging.getLogger("app.%s" % __name__)

class G:
    conn = None

def drop_table(name):

    c = G.conn.cursor()

    try:
        c.execute("DROP TABLE %s" % name)
    except lite.OperationalError as e:
        logger.error(e)
    else:
        logger.info("Table %s removed" % name)

def create_table(name="OST_STATS", drop = False):
    c = G.conn.cursor()

    if drop:
        drop_table(name)

    # create table
    try:
        c.execute('''
                CREATE TABLE %s(
                    Timestamp TEXT,
                    Metric TEXT,
                    Target TEXT,
                    Attributes TEXT)
                ''' % name)
    except lite.OperationalError as e:
        logger.warn(e)
    else:
        logger.info("Table %s created" % name)


def insert_row(metric, stats):
    c = G.conn.cursor()
    try:
        for target, attr in stats.iteritems():
            ts = attr["snapshot_time"]
            c.execute("INSERT INTO OST_STATS VALUES (?, ?, ?, ?)",
                    (metric, ts, target, str(attr)))

        G.conn.commit()
    except lite.Error as e:
        logger.error(e)
    else:
        logger.debug("Insert OK from %s" % metric)

def db_init(url, initTable=False):

    if G.conn is None:
        G.conn = lite.connect(url)

    create_table(drop = initTable)

def db_close():
    if G.conn is not None:
        G.conn.close()


