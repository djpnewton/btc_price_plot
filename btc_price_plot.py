import os
import time
import datetime
from matplotlib.dates import date2num
import matplotlib.gridspec as gridspec
from matplotlib.finance import candlestick_ohlc
from matplotlib.ticker import FormatStrFormatter
import matplotlib.pyplot as plt
import matplotlib
import io

def unixtimestamp_to_mpldatenum(ts):
    # convert from unix timestamp to matplotlib date
    return date2num(datetime.datetime.fromtimestamp(ts))

def days_to_unixtimestamp(days):
    return days * 24 * 60 * 60

def str_to_days(s):
    # 1d, 2w, 2m, 1y etc...
    multiplier, timespan = int(s[0]), s[1]
    if timespan == 'h':
        return multiplier / 24.0
    if timespan == 'd':
        return multiplier
    if timespan == 'w':
        return multiplier * 7
    if timespan == 'm':
        return multiplier * 30
    return multiplier * 365

# clump data into [date, open, high, low, close, volume]
def clump_data(count, start_date, stop_date, trades, volume_in_fiat=False):
    period_size = (stop_date - start_date) / count
    period_start = start_date
    data = [None] * count
    raw_index = 0
    for i in range(count):
        period_mid = period_start + period_size / 2
        period_mid = unixtimestamp_to_mpldatenum(period_mid)
        data[i] = [period_mid, 0, 0, 0, 0, 0]
        # fast forward to next relevant trade
        while raw_index < len(trades) and trades[raw_index]['date'] < period_start:
            raw_index += 1
        # update current clump data point with raw data entry
        if raw_index < len(trades):
            if trades[raw_index]['date'] < period_start + period_size:
                current_price = trades[raw_index]['price']
                data[i] = [period_mid, current_price, current_price, current_price, current_price, 0]
                while raw_index < len(trades) and trades[raw_index]['date'] < period_start + period_size:
                    current_price = trades[raw_index]['price']
                    data[i][4] = current_price
                    if current_price < data[i][3]:
                        data[i][3] = current_price
                    elif current_price > data[i][2]:
                        data[i][2] = current_price
                    if volume_in_fiat:
                        data[i][5] += trades[raw_index]['amount'] * trades[raw_index]['price']
                    else:
                        data[i][5] += trades[raw_index]['amount']
                    raw_index += 1
        period_start += period_size
    # remove empty price entries
    for i in range(len(data)-1, -1, -1):
        if data[i][1] == 0 and data[i][2] == 0 and data[i][3] == 0 and data[i][4] == 0:
            data.pop(i)
    return data

def trade_data_to_ohlcv(data, start_date, end_date, period_count, volume_in_fiat=False):
    ohlcv = clump_data(period_count, start_date, end_date, data, volume_in_fiat)
    return ohlcv

def plot(width, height, start_date, end_date, period_count, ohlcv, bgcolor=None, show_volume=True, volume_is_primary=False):
    dpi = 100.0
    days = end_date - start_date
    bar_width = days / period_count * 0.8

    # two subplots, shared x axis, top one larger bigger
    fig = plt.figure()
    gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1])
    ax1 = plt.subplot(gs[0])
    ax1.tick_params(axis='both', which='major', labelsize=8)
    if show_volume:
        ax2 = plt.subplot(gs[1], sharex=ax1)
        ax2.tick_params(axis='both', which='major', labelsize=8)
        plt.setp(ax1.get_xticklabels(), visible=False)
    else:
        plt.setp(ax1.get_xticklabels(), visible=True)

    # misc figure settings
    fig.set_dpi(dpi)
    fig.set_size_inches(width / dpi, height / dpi)
    plt.xticks(rotation=45, horizontalalignment='right')
    if bgcolor:
        ax1.patch.set_facecolor(bgcolor)
        if show_volume:
            ax2.patch.set_facecolor(bgcolor)

    if volume_is_primary:
        # draw volume bars
        dates = [x[0] for x in ohlcv if x[1] >= x[4]]
        vol = [x[5] for x in ohlcv if x[1] >= x[4]]
        ax1.bar(dates, vol, color='r', alpha=0.5, width=bar_width, align='center')
        dates = [x[0] for x in ohlcv if x[1] < x[4]]
        vol = [x[5] for x in ohlcv if x[1] < x[4]]
        ax1.bar(dates, vol, color='#7CFC00', alpha=0.5, width=bar_width, align='center')
    else:
        # draw candlesticks
        candlestick_ohlc(ax1, ohlcv, width=bar_width, colorup='#7CFC00')
        ax1.yaxis.set_major_formatter(FormatStrFormatter('$%d'))
    
    if show_volume:
        # draw volume bars
        dates = [x[0] for x in ohlcv if x[1] >= x[4]]
        vol = [x[5] for x in ohlcv if x[1] >= x[4]]
        ax2.bar(dates, vol, color='r', alpha=0.5, width=bar_width, align='center')
        dates = [x[0] for x in ohlcv if x[1] < x[4]]
        vol = [x[5] for x in ohlcv if x[1] < x[4]]
        ax2.bar(dates, vol, color='#7CFC00', alpha=0.5, width=bar_width, align='center')

    # set date style for xaxis
    ax1.xaxis_date()
    ax1.autoscale_view()

    # allow gaps before and after data
    ax1.set_xlim(start_date, end_date)

    fig.tight_layout(pad=0)

    # make subplots close to each other
    fig.subplots_adjust(hspace=0)
    if show_volume:
        plt.setp((ax2.get_yticklabels()[-1]), visible=False)

    #plt.show()
    buf = io.BytesIO()
    if bgcolor:
        plt.savefig(buf, transparent=False, facecolor=bgcolor)
    else:
        plt.savefig(buf, transparent=True)
    return buf

def plot_price_vs_volume(width, height, start_date, end_date, period_count, ohlcv_price, ohlcv_vol, bgcolor=None):
    dpi = 100.0
    days = end_date - start_date
    bar_width = days / period_count * 0.8

    # two subplots, shared x and y axis
    fig = plt.figure()
    ax1 = plt.subplot()
    ax1.tick_params(axis='both', which='major', labelsize=8)

    # misc figure settings
    fig.set_dpi(dpi)
    fig.set_size_inches(width / dpi, height / dpi)
    plt.xticks(rotation=45, horizontalalignment='right')
    if bgcolor:
        ax1.patch.set_facecolor(bgcolor)

    # draw volume bars
    dates = [x[0] for x in ohlcv_vol if x[1] >= x[4]]
    vol = [x[5] for x in ohlcv_vol if x[1] >= x[4]]
    ax1.bar(dates, vol, color='r', alpha=0.5, width=bar_width, align='center')
    dates = [x[0] for x in ohlcv_vol if x[1] < x[4]]
    vol = [x[5] for x in ohlcv_vol if x[1] < x[4]]
    ax1.bar(dates, vol, color='#7CFC00', alpha=0.25, width=bar_width, align='center')
    ax1.yaxis.set_major_formatter(FormatStrFormatter('$%d'))

    # draw candlesticks
    ax2 = ax1.twinx()
    candlestick_ohlc(ax2, ohlcv_price, width=bar_width, colorup='#7CFC00')
    ax2.yaxis.set_major_formatter(FormatStrFormatter('$%d'))
    
    # set date style for xaxis
    ax1.xaxis_date()
    ax1.autoscale_view()

    # allow gaps before and after data
    ax1.set_xlim(start_date, end_date)

    fig.tight_layout(pad=0)

    #plt.show()
    buf = io.BytesIO()
    if bgcolor:
        plt.savefig(buf, transparent=False, facecolor=bgcolor)
    else:
        plt.savefig(buf, transparent=True)
    return buf

def read_data_since(csv_gz_filename, since, now, period_count, volume_in_fiat=False):
    processed_filename = csv_gz_filename + '.processed'

    # download file if it does not exist
    if not os.path.exists(csv_gz_filename):
        print csv_gz_filename, 'does not exist, downloading...'
        import urllib2
        r = urllib2.urlopen('http://api.bitcoincharts.com/v1/csv/' + csv_gz_filename)
        open(csv_gz_filename, 'wb').write(r.read())
        # remove invalidated processed file
        if os.path.exists(processed_filename):
            os.path.remove(processed_filename)

    import cPickle as pickle
    if not os.path.exists(processed_filename):
        print 'reading', csv_gz_filename
        import gzip
        import csv
        entries = []
        with gzip.open(csv_gz_filename, 'rb') as f:
            reader = csv.reader(f)
            for row in reader:
                timestamp = int(row[0])
                price = float(row[1])
                amount = float(row[2])
                if timestamp >= since:
                    entries.append({'date': timestamp, 'price': price, 'amount': amount})
        print 'generating ohlcv (since: %d)' % since
        ohlcv = trade_data_to_ohlcv(entries, since, now, period_count, volume_in_fiat)
        print 'writing', processed_filename
        pickle.dump(ohlcv, open(processed_filename, 'wb'))
        return ohlcv
    else:
        print 'reading', processed_filename
        return pickle.load(open(processed_filename, 'rb'))

def demo(input_filename, output_filename='test.png', width=600, height=400, timespan='2m', period_count=30):
    now = time.time()
    earliest = 0
    if timespan != 'all':
        earliest = now - days_to_unixtimestamp(str_to_days(timespan))
    ohlcv = read_data_since(input_filename, earliest, now, period_count)
    start_date = unixtimestamp_to_mpldatenum(earliest)
    end_date = unixtimestamp_to_mpldatenum(now)
    buf = plot(width, height, start_date, end_date, period_count, ohlcv, bgcolor='lightgrey')
    buf.seek(0)
    open(output_filename, 'wb').write(buf.read())
    print 'saved %s' % output_filename

def lbc_vol_vs_bitstamp_price(width=1200, height=600, timespan='4y', period_count=204):
    now = time.time()
    earliest = 0
    if timespan != 'all':
        earliest = now - days_to_unixtimestamp(str_to_days(timespan))
    # use data files from http://api.bitcoincharts.com/v1/csv/
    ohlcv_price = read_data_since('bitstampUSD.csv.gz', earliest, now, period_count)
    ohlcv_vol = read_data_since('localbtcUSD.csv.gz', earliest, now, period_count, volume_in_fiat=True)
    start_date = unixtimestamp_to_mpldatenum(earliest)
    end_date = unixtimestamp_to_mpldatenum(now)
    buf = plot_price_vs_volume(width, height, start_date, end_date, period_count, ohlcv_price, ohlcv_vol, bgcolor='lightgrey')
    buf.seek(0)
    output_filename = 'lbc_vol_vs_bitstamp_price.png'
    open(output_filename, 'wb').write(buf.read())
    print 'saved %s' % output_filename

if __name__ == '__main__':
    import sys
    # use data files from http://api.bitcoincharts.com/v1/csv/
    filename = 'bitstampUSD.csv.gz'
    timespan = '2m'
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        if len(sys.argv) > 2:
            timespan = sys.argv[2]
        demo(input_filename=filename, timespan=timespan)
    else:
        lbc_vol_vs_bitstamp_price()
