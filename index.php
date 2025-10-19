<?php
$app_name = "intfar";

$ports_file = dirname(__DIR__) . "/flask_ports.json";
$ports_map = json_decode(file_get_contents($ports_file), true);
$port = $ports_map[$app_name];

$url = "https://mhooge.com:" . $port . "/" . $app_name;

$redir = "";
if ($_SERVER["REQUEST_URI"] != "/" . $app_name . "/") {
    $expl = explode("/", $_SERVER["REQUEST_URI"]);
    $redir = "";
    for ($index = 2; $index < count($expl); $index++) {
        $redir = $redir . "/" . $expl[$index];
    }
    $redir = $url . $redir;
}
else {
    $redir = $url;
}

header("Location: " . $redir);
?>