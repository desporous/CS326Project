// Handles loading and replying to comments. Retrieves comments for given trip id using AJAX.

var trip_id = 6;

$(document).ready(function(){
	console.log('Doc ready');
	$.ajax({
		type: "get",
		url: "http://localhost:8000/trip/6/comments",
		contentType: "application/json",
		success: function(data) {
			console.log('Received response');
			console.log(data);
			
			// mapping of comment ids to comment objects
			var comments = new Map();
			
			for (var i = 0; i < data.length; i++) {
				console.log('Elem ' + i + ' is ' + data[i].id);
				
				// list of ids of replies to this comment
				data[i].replies = []
				
				comments.set(data[i].id, data[i]);
				console.log(comments.size);
				console.log(comments.get(data[i].id));
			}
			
			// list of comment ids that are base comments
			base_comments = []
			
			// build parent associations
			for (const id of comments) {
				console.log('id is ' + id[0]);

				if (comments.get(id[0]).parent === 0) {
					base_comments.push(id[0]);
				} else {
					comments.get(comments.get(id[0]).parent).replies.push(id[0]);
				}
			}

			var comment_header = document.getElementById('comments-header');
			
			// render comment threads
			for (var i = 0; i < base_comments.length; i++) {
				var rendered_dom = renderThread(comments, base_comments[i], 0);
				comment_header.append(rendered_dom); // TODO: this will add them in reverse order of creation
			}
		},
		error: function(){
			console.log('AJAX error');
		}
	});
});

// renders comment thread starting with given id. comments is a mapping of ids to comment objects. Depth is the depth of the current thread. Returns rendered DOM element
function renderThread(comments, id, depth) {
	var div = document.createElement('div');
	div.setAttribute('id', 'comment-' + comments.get(id).id);
	div.setAttribute('padding-left', depth * 30);
	div.className = 'comment';
	div.style.backgroundColor = '#CCC';
	
	div.innerHTML = '<p>' + comments.get(id).author_name + '<p>';
	
	if (comments.get(id).parent !== 0) {
		div.innerHTML = '<p>Replying to ' + comments.get(comments.get(id).parent).author_name + '</p>';
	}
	
	div.innerHTML = div.innerHTML + '<p>' + comments.get(id).timestamp + '</p>' + '<p>' + comments.get(id).text + '</p>';
	
	for (var i = 0; i < comments.get(id).replies.length; i++) {
			renderThread(comments, comments.get(id).replies[i], depth + 1);
	}
	return div;
}
/*
var comments = document.getElementsByClassName('comment');
var reply_btns = document.getElementsByClassName('comment-reply-btn');

console.log('Found ' + reply_btns.length + ' buttons');

// note: I am not good at Javascript. Please feel free to revise (and better yet, tell me how I can make it better)
for (var i = 0; i < reply_btns.length; i++) {
	reply_btns[i].dataset.replied = 0;
	handleElement(i);
}
	/*reply_btns[i].dataset.index = i;
	console.log('Button created for comment ' + reply_btns[i].dataset.dataCommentId);

	reply_btns[i].onclick = function(e) {
		console.log('You clicked button for comment ' + e.target.dataset.index);
		var reply = document.createElement('div');
		reply.innerHTML = '<input type="text" placeholder="Comment" class="form-control" />';
		e.target.appendChild(reply);
	}
	
}

function onClickReply(comment_index) {
	console.log(comment_index);
	
}*/
/*
function handleElement(i) {
    reply_btns[i].onclick=function() {
		console.log('Comment ' + i + ' clicked. Replied = ' + reply_btns[i].dataset.replied);
		// check comment has not been replied to
		if (reply_btns[i].dataset.replied === '0') {
			reply_btns[i].dataset.replied = '1';
			var reply_div = document.createElement('div');
			var text_input = document.createElement('input');
			var send_btn = document.createElement('button');
			
			// have it send a post when clicked  TODO: USE DJANGO FORM
			send_btn.onclick = function() {
				console.log('User is sending ' + text_input.value);
			}
			
			reply_div.appendChild(text_input);
			reply_div.appendChild(send_btn);
			//reply.innerHTML = '<input type="text" placeholder="Comment" class="form-control" /><button type="button">Send</button>';
			
			comments[i].appendChild(reply_div);
		}
    };
}*/
