import sys
sys.path.append('.')
sys.path.append('lib')
from optparse import OptionParser
from couchdbkit import Server
import smtplib
import string

sender = 'qe@couchbase.com'
receivers = ['karan@couchbase.com']
mail_server = '10.1.0.118'

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
        tests = 0
        errors = 0
        server = Server(options.node)
        db = server.get_db(options.database)
        doc = get_build_doc(db, options.build)
        doc_content = db.open_doc(doc['_id'])
        print "List of tests against %s are %s " % (options.build, doc_content['_attachments'].keys())

        for attachment, value in doc_content['_attachments'].items():
            error_count = 0
            tests_count = 0
            print "Fetching attachment %s " % attachment
            file = db.fetch_attachment(doc, attachment)
            file = file.encode('ascii', 'ignore')
            file = file.split(" ")
            for entry in file:
                if entry.startswith("errors"):
                    error_count = int(entry.replace('"', '').split('=')[-1])
                    errors += error_count

                if entry.startswith("tests"):
                    tests_count = int(entry.replace('"', '').split('=')[-1])
                    tests += tests_count

            print "Testname: %s, passed: %s, failed: %s" % (attachment.split('.xml')[0], tests_count-error_count,
                                                            error_count)


        try:
            text = "Passed %s out of %s tests on %s build" % (tests-errors, tests, options.build)
            BODY = string.join((
                "From: %s" % sender,
                "To: %s" % receivers,
                "Subject: %s" % '2.0.0 trunk status' ,
                "",
                text
                ), "\r\n")

            smtpObj = smtplib.SMTP(mail_server)
            smtpObj.sendmail(sender, receivers, BODY)
            print "Successfully sent email"
            smtpObj.quit()
        except Exception as ex:
            print ex.message
            print "Error: unable to send email"

    except Exception as ex:
        print ex.message
        print "unable to connect to %s " % options.node
