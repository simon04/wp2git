import std.stdio;
import std.process;
import std.stream;
import std.string;
import std.file;
import litexml;

int main(string[] args)
{
	if (args.length != 2)
	{
		writefln("Usage: %s Article_name", args[0]);
		return 1;
	}

	string name = args[1];
	if (name.length>=2 && name[0]=='"' && name[$-1]=='"')
		name = name[1..$-1]; // strip quotes

	if (spawnvp(P_WAIT, "curl", ["curl", "-d", "", "http://en.wikipedia.org/w/index.php?title=Special:Export&pages=" ~ name, "-o", "history.xml"]))
		throw new Exception("curl error");

	auto xml = new XmlDocument(new File("history.xml"));

	string data;
	foreach (child; xml[0]["page"])
		if (child.tag=="revision")
		{
			string summary = child["comment"].toString;
			string text = child["text"].toString;
			data ~= 
				"commit master\n" ~ 
				"committer <" ~ (child["contributor"]["username"] ? child["contributor"]["username"].toString : child["contributor"]["ip"].toString) ~ "> now\n" ~ 
				"data " ~ .toString(summary.length) ~ "\n" ~ 
				summary ~ "\n" ~ 
				"M 644 inline " ~ name ~ ".txt\n" ~ 
				"data " ~ .toString(text.length) ~ "\n" ~ 
				text ~ "\n" ~ 
				"\n";
		}
	
	write("fast-import-data", data);
}
