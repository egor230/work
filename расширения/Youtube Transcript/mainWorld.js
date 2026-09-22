window.addEventListener( "message", ( event ) => {
	if( event.source === window && event.data.type && event.data.type === "get yt data" ){
		var device = yt.config_.DEVICE;
		var clientVersion = yt.config_.INNERTUBE_CLIENT_VERSION;
		
		window.postMessage(
			{ 'type': 'put yt data', 'value': { clientVersion, device }},
			"*"
		);
	}
});