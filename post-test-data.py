import sys
sys.path.append('.')
sys.path.append('lib')
from optparse import OptionParser
from couchdbkit import Server
import time
import os


def get_doc(db, build):
    doc_id = ''
    rev_id = ''
    doc = {}
    for row in db.view('builds/results'):
        if row['key'] == options.build:
            print "Found doc for build %s " % build
            doc_id = row['id']
            rev_id = row['value']
            print row
            doc = {'_id':doc_id, '_rev':rev_id}
            break
    else:
        print "Creating new doc for build %s " % build
        doc = {'build': build, 'time':time.time()}
        res = db.save_doc(doc, force_update=True)
        doc_id = res["id"]
        rev_id = res["rev"]
        msg = "inserted document with id : %s and rev : %s"
        print msg % (doc_id, rev_id)
        doc = {'build': build, 'time':time.time(), '_id':doc_id, '_rev':rev_id}

    return doc

def get_xml_files(options):
    files_list = []
    if options.all is not '':
        for r,d,f in os.walk("."):
            for files in f:
                if files.endswith(".xml") and files.startswith('report'):
                    file_path = os.path.join(r,files)
                    print "Found test xml file : {0}".format(file_path)
                    files_list.append(file_path)
    else:
        print "Will load this test xml file : {0}".format(options.input)
        files_list.append(options.input)

    return files_list

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
    parser.add_option("-i", "--input",
                      dest="input", help="xml file to be posted",
                      default="test.xml")
    parser.add_option("-a", "--all",
                  dest="all", help="post all xml file",
                  default="")

    options, args = parser.parse_args()

    try:
        server = Server(options.node)
        db = server.get_or_create_db(options.database)
        doc = get_doc(db, options.build)

        files_list = get_xml_files(options)
        for file in files_list:
            datasource = open(file)
            name = file.split('-')[-1]
            print "inserting attachment with name : {0}".format(name)
            db.put_attachment(doc, datasource.read(), name, "text/xml")
            datasource.close()

    except Exception as ex:
        print ex.message
        print "unable to connect to %s " % options.node
