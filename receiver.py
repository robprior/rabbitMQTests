#!/usr/bin/env python
import re
import argparse
import sys
import pika
import imp
import os
import ConfigParser

config = ConfigParser.ConfigParser()
config.read("./rabbitMQtests.config")

class Receiver(object):
	def __init__(self):	  
	  #setup the connection
          sslOptions = {}
          sslOptions["ca_certs"]  = os.path.abspath(config.get('general', "CA_CERT_FILE"))
          sslOptions["certfile"]  = os.path.abspath(config.get('general', 'CLIENT_CERT_FILE'))
          sslOptions["keyfile"]   = os.path.abspath(config.get('general', 'CLIENT_KEY_FILE'))

          self.connection = pika.BlockingConnection(pika.ConnectionParameters(
                                                     host=config.get('general', 'HOST'),
                                                     port=int(config.get('general', 'PORT')),
                                                     ssl=config.getboolean('general', 'USE_SSL'),
                                                     ssl_options = sslOptions
                                                     )
                                                    )
	  self.channel = self.connection.channel()
	
	  #set up directory where RPC functions will be stored
	  self.pathToRPCFuncs = os.path.abspath(config.get('general', 'RECEIVE_RPC_FUNCS_DIR'))

	#Function to setup basic receives either from a queue or exchange
	#If from an exchange, a temporary queue is created for this receiver
	def basicReceive(self, args):
	  outputMessage = "Waiting for messages from "

	  #due to the way arg parser works, arguments are parsed as a list of strings (even if number of args is specified as 1)
	  #we know that there will always only be one source queue or exchange we can read from at a time
	  #this converts list of strings to just a string
	  args.source = args.source[0]

	  if(args.receiveFromQueue):
		self.channel.queue_declare(queue=args.source)
		self.channel.basic_consume(self.basicCallback,
					   queue=args.source)
	 	outputMessage += "queue "
	  else:
   	  	self.channel.exchange_declare(exchange=args.source,
	  	     	                      type='fanout')
		result = self.channel.queue_declare(exclusive=True)
		queue_name = result.method.queue
		self.channel.queue_bind(exchange=args.source,
        		           queue=queue_name)
		self.channel.basic_consume(self.basicCallback,
				      queue=queue_name)
		outputMessage += "exchange "

	  outputMessage += args.source
	  print outputMessage

	  try:
  	  	self.channel.start_consuming()
	  except KeyboardInterrupt:
		print "\nExiting"
		sys.exit()

	#used with basic receive to print any messages sent
	def basicCallback(self, ch, method, properties, body):
	  print "Received %r" % (body,)
	  ch.basic_ack(delivery_tag = method.delivery_tag)

	#function to setup up RPC requests
	def rpcRequestReceive(self, args):
	  self.channel.queue_declare(queue=config.get('general', 'RPC_REQUEST_Q'))
	  self.channel.basic_consume(self.rpcRequestCallback,
				     queue=config.get('general', 'RPC_REQUEST_Q'))
	  print "Begining rpc request Receive"

	  try:
  	  	self.channel.start_consuming()
	  except KeyboardInterrupt:
		print "\nExiting"
		sys.exit()

	#function to handle RPC requests
	#dynamically loads modules from folder specified in config file
	#(this means that functions can be modified or created while the receiver is running)
	def rpcRequestCallback(self, ch, method, properties, body):
	  print "Received rpc %r" %(body,)
	  #sender sends function and arguments in comma seperated list with function,arg1,arg2.....
	  commandToParse = body.split(",");
	  function = commandToParse[0]
	  args = commandToParse[1:]
	  print "Attempting calling function %s with args %r" % (function, args,)
	  try:
		  #attempt to find the module
		  fileHandle, pathName, impDescrip = imp.find_module(function, [self.pathToRPCFuncs])
		  #if it exsists load the module
		  module = imp.load_module(function, fileHandle, pathName, impDescrip)
		  #find the specified function and call it
		  result = getattr(module, function)(args)
		  print "Print function returned " + str(result)
	  except Exception as e:
		  print "Encountered an error sending error response to sender"
		  result = e

	  self.channel.basic_publish(exchange='',
        	             	     routing_key=properties.reply_to,
	        	             properties=pika.BasicProperties(correlation_id = \
                		                                     properties.correlation_id),
		                     body=str(result))
          self.channel.basic_ack(delivery_tag = method.delivery_tag)

	#function to handle RPC create requests
	#allows new functions to be made in /rpcServerFunctions
	def rpcCreate(self, args):
	  self.channel.queue_declare(queue=config.get('general', 'RPC_CREATE_Q'))
	  self.channel.basic_consume(self.rpcCreateCallback,
				     queue=config.get('general', 'RPC_CREATE_Q'))
	  print "Begining rpc create Receive on queue:"
	  print self.consts.rpcCreateQueueName
	  try:
  	  	self.channel.start_consuming()
	  except KeyboardInterrupt:
		print "\nExiting"
		sys.exit()

	def rpcCreateCallback(self, ch, method, properties, body):
	  print "Got a new Function"
	  print body
	  #search file for first funtion decleration, that becomes the name of the file
	  regex = re.compile("def\s(.*)\(") #look for string "def *(" only taking the * where the * is any number of chars
	  functionName = regex.search(body).group(1)
	  fileName = self.pathToRPCFuncs  + functionName + ".py"
	  print "File to be created:"
	  fileName = os.path.abspath(fileName)
	  print fileName
	  try:
		with open(fileName, "w") as f:
			f.write(body)
	  except Exception as e:
	  		print "Error writing file:"
	  		print e
	  print "Succesfully opened file"
          self.channel.basic_ack(delivery_tag = method.delivery_tag)
	  print "Finished new function creation"

#Main
receiver = Receiver()

#Top level parser
parser = argparse.ArgumentParser(description='Receive messages from a given  AMQP queue or exchange')
subparsers = parser.add_subparsers(dest='command')

#Basic receive
receive_parser = subparsers.add_parser('receive')
receive_parser.add_argument('source', nargs=1,  help='Specifies a source queue or exchange (default is queue change with --exchange)')
receive_parser.add_argument('--exchange', dest='receiveFromQueue', action='store_const',
                   const= False, default= True,
                   help='An exchange will be used. Any receivers/consumers will see all messages from this exchange. A temporary rabbitMQ named queue will be created specifically for this instance of receiver and will be destroyed on exit')
receive_parser.set_defaults(func=receiver.basicReceive)

#handle RPC requests
rpc_parser = subparsers.add_parser('rpc')
rpc_parser.add_argument('rpcMode', choices=['request', 'create'],
		    help='Sets up this receiver to handle remote procedure calls. The request mode specifies functions should just be called where create allows for new functions to be created. The list of availavle functions resides in ./rpcServerFunctions. These functions can be modified/new ones created while a receiver is running in request mode. Caveat: for creation, files with multiple functions will use the name of the first function in the file.')
rpc_parser.set_defaults(func=receiver.rpcRequestReceive)

args = parser.parse_args()

if args.command == 'rpc':
	if args.rpcMode == 'call':
		args.func = receiver.rpcRequestReceive
	elif args.rpcMode == 'create':
		args.func = receiver.rpcCreate
args.func(args)
