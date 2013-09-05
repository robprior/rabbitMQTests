def factorial(args):
	if(len(args) == 1):
		args = args[0]
	return doFactorial(int(args))

def doFactorial(n):
	if(n <= 1):
		return 1;
	else:
		return n*doFactorial(n-1)
	
