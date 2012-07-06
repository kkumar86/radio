from optparse import OptionParser
from couchdbkit import Server
import smtplib
import string
from lxml import etree
import StringIO

sender = 'qe@couchbase.com'
receivers = ['farshid@couchbase.com', 'peter@couchbase.com', 'karan@couchbase.com']
#receivers = ['karan@couchbase.com']
mail_server = '10.1.0.118'
results = {}
threshold = 0.15

single_node_xmls = ['memcapable' , 'expirytests', 'drainratetests', 'deletebuckettests',
                    'setgettests', 'createbuckettests', 'recreatebuckettests']

test_classes = ['basic', 'failover', 'rebalance', 'swaprebalance', 'views', 'warmup', 'xdcr']

#TODO: dont hardcode
url_mapping = {'basic': ['single-node-2-0-centos-64'],
               'failover': ['centos-failover-tests'],
               'swaprebalance': ['centos-64-2.0-swap-rebalance'],
               'warmup': ['centos-64-2.0-rebalance-tests'],
               'xdcr': ['Centos-64-XDCR-Smoke-tests'],
               'views': ['centos-64-2.0-new-view-tests', 'centos-64-2.0-view-tests', 'centos-64-2.0-new-view-tests'],
               'rebalance': ['centos-64-2.0-rebalance-tests', 'centos-64-2.0-new-rebalance',
                             'centos-64-2.0-swap-rebalance']}

jenkins_url = 'http://qa.hq.northscale.net/job'

def get_build_doc(db, build):
    doc_id = ''
    rev_id = ''
    doc = {}
    for row in db.view('builds/results'):
        if row['key'] == build:
            print "Found doc for build %s " % build
            print row
            doc_id = row['id']
            rev_id = row['value']
            doc = {'_id':doc_id, '_rev':rev_id}
            break
    else:
        print "No build doc found for %s" % build
        exit(1)
    return doc

def get_detailed_status(options):
    total_tests = 0
    total_errors = 0
    server = Server(options.node)
    db = server.get_db(options.database)
    doc = get_build_doc(db, options.build)
    doc_content = db.open_doc(doc['_id'])
    tests_list = doc_content['_attachments'].keys()
    # TODO: Check for number of tests that ran
    print "List of tests against %s are %s " % (options.build, tests_list)
    failed_tests = []
    # Data struct to store information per test_class (attachment)
    # {test_name:{tests:<int>, errros:<int>, time:<float>}}
    test_data = {}
    for attachment, value in doc_content['_attachments'].items():
        errors_count = 0
        tests_count = 0
        print "Fetching attachment %s " % attachment
        file = db.fetch_attachment(doc, attachment)
        file = file.encode('ascii', 'ignore')
        xmldoc =  etree.parse(StringIO.StringIO(file))
        root = xmldoc.getroot()
        for child in root:
            attributes = child.attrib
            for childish in child:
                # To print the error
                #print childish.text
                failed_tests.append(attributes.get('name'))
        attributes = root.attrib
        # To get root element attributes
        #print attributes
        name = attributes.get('name')
        errors_count = int(attributes.get('errors'))
        tests_count = int(attributes.get('tests'))
        total_tests += tests_count
        total_errors += errors_count
        print "Testname: %s, passed: %s, failed: %s" % (name, tests_count-errors_count,
                                                        errors_count)
        test_data[name] = {}
        test_data[name]['tests'] = tests_count
        test_data[name]['errors'] = errors_count
        test_data[name]['time'] = float(attributes.get('time'))

    #print test_data
    text = "Passed %s out of %s tests on %s build\n" % (total_tests-total_errors, total_tests,
                                                        options.build)
    num_failed = len(failed_tests)
    if num_failed > 0:
        text += "\nList of Failed tests:\n"
        for i in range(num_failed):
            text += "%s: %s\n" % (i+1, failed_tests[i])

    print text
    return test_data

def initialize_results():
    for test in test_classes:
        results[test] = {}
        results[test]['tests'] = 0
        results[test]['errors'] = 0
        results[test]['time'] = 0
        results[test]['status'] = 'None'

def update_results(key, data):
    if key is '':
        return
    results[key]['tests'] += data['tests']
    results[key]['errors'] += data['errors']
    results[key]['time'] += data['time']

def rules_engine(data={}):
    initialize_results()
    # Groupings
    for test, data in data.items():
        key = ''
        if test.startswith('rebalance') or test.startswith('rebalancetests'):
            key = 'rebalance'
        elif test.startswith('swaprebalance'):
            key = 'swaprebalance'
        elif test.startswith('view'):
            key = 'views'
        elif test.startswith('xdcr'):
            key = 'xdcr'
        elif test.startswith('failover'):
            key = 'failover'
        elif test.startswith('warmup'):
            key = 'warmup'
        else:
            key = 'basic'
        update_results(key, data)

def get_trunk_status():
    for test, data in results.items():
        if data['errors'] > threshold *  data['tests']:
            data['status'] = 'RED'
        elif data['tests'] == 0:
            data['status'] = 'N/A'
        else:
            data['status'] = 'GREEN'

def send_email(build):

    num_tests = len(test_classes)
    text = ''
    totals = 0
    errors = 0
    build_status = 'GREEN'
    if num_tests > 0:
        text += "\nTest details (centos-64):\n"
        for i in range(num_tests):
            test = test_classes[i]
            status = results[test]['status']
            #text += "%s: %8s\n" % (test, status)
            if status is 'RED':
                text += "%s: **** %s ****\n" % (test, status)
                urls = url_mapping[test]
                for url in urls:
                    text += jenkins_url + '/' + url + '\n'
                text += '\n'
            else:
                text += "{0}: {1:8s}\n\n".format(test, status)
            totals += results[test]['tests']
            errors += results[test]['errors']
        #text += "\nTest details (ubuntu-64):\n"
        #text += " n/a"
        #text += "\nTest details (windows-64):\n"
        #text += " n/a"
        #text += "\nTest details (osx):\n"
        #text += " n/a\n"
    if results['basic']['status'] is 'RED':
        build_status = 'RED'
    if errors > totals* threshold:
        build_status = 'RED'

    if build_status is 'RED':
        msg = 'Do NOT integrate until you receive a trunk status GREEN email! \n'
    else:
        msg = 'You can integrate changes after: \n'
        msg += ' * all unit tests pass\n'
        msg += ' * make simple-test passes\n'

    text = msg + text
    text += "Trunk green process for 2.0:-\n"
    text += "http://hub.internal.couchbase.com/confluence/display/QA/2.0+trunk+health\n\n"

    text += "Disclaimer: In some cases, tests can fail because of intermittent\n" \
            "infrastructure problems such as off-line slaves or power outages."
    print text
    try:
        BODY = string.join((
            "From: %s" % sender,
            "To: %s" % receivers,
            "Subject: %s %s: %s" % ('Trunk status for ', build, build_status) ,
            "", text
            ), "\r\n")

        smtpObj = smtplib.SMTP(mail_server)
        smtpObj.sendmail(sender, receivers, BODY)
        print "Successfully sent email"
        smtpObj.quit()
    except Exception as ex:
        print ex.message
        print "Error: unable to send email"


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-n", "--node", dest="node", default="http://127.0.0.1:5984",
                      help="couchdb ip , defaults to 127.0.0.1:5984")
    parser.add_option("-d", "--database",
                      dest="database", help="db name in couchdb",
                      default="tmp")
    parser.add_option("-b", "--build",
                      dest="build", help="build information",
                      default="1.8.1")
    options, args = parser.parse_args()

    try:
        test_data = get_detailed_status(options)
        rules_engine(test_data)
        get_trunk_status()
        send_email(options.build)

    except Exception as ex:
        print ex.message
        print "unable to connect to %s " % options.node
